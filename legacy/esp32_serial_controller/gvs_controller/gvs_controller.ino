// GVS controller firmware (ESP32-C3). Software safety layer for the command
// input of an external analog GVS front end. See ../README.md.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <SD.h>
#include <WiFi.h>
#include <WebServer.h>
#include "safety.h"

// ---- pins (ESP32-C3) ----
static const int PIN_PWM   = 4;   // LEDC output
static const int PIN_ESTOP = 5;   // input, pull-up, LOW = E-stop
static const int PIN_SCK   = 6;
static const int PIN_MISO  = 7;
static const int PIN_MOSI  = 10;
static const int PIN_CS    = 3;

// ---- state ----
static float    maxDuty = DEFAULT_MAX_DUTY;
static String   deviceName = "gvs-controller";
static String   wifiSsid, wifiPass;
static bool     sdOk = false;
static bool     armed = false;
static uint32_t armedAt = 0;
static bool     estopLatched = false;

static bool     stimActive = false;
static uint32_t stimStart = 0, stimDur = 0;
static uint32_t stimPeak = 0;          // peak duty counts
static bool     everStimmed = false;
static uint32_t lastEnd = 0;           // millis when previous stim ended
static uint32_t history[MAX_STIMS_PER_HOUR];
static int      histCount = 0;         // number of valid entries (<= MAX)
static int      histHead = 0;          // next write index

static WebServer server(80);
static bool serverStarted = false;
static String serialBuf;
static bool serialOverflow = false;

static void outDuty(uint32_t d) {
  if (d > PWM_MAX_COUNTS) d = PWM_MAX_COUNTS;
  ledcWrite(PIN_PWM, d);
}

static void endStim() {
  outDuty(0);
  if (stimActive) { stimActive = false; lastEnd = millis(); }
}

static int stimsLastHour() {
  uint32_t now = millis();
  int n = 0;
  for (int i = 0; i < histCount; i++) if ((uint32_t)(now - history[i]) < HOUR_MS) n++;
  return n;
}

static void recordStim() {
  history[histHead] = millis();
  histHead = (histHead + 1) % MAX_STIMS_PER_HOUR;
  if (histCount < MAX_STIMS_PER_HOUR) histCount++;
}

static String clean(const String& s) {
  String o; 
  for (size_t i = 0; i < s.length() && i < 32; i++) {
    char c = s[i];
    o += (c == ',' || c == '"' || c == '\n' || c == '\r') ? '_' : c;
  }
  return o;
}

static void logTrial(const String& bucket, float inten, uint32_t duty, uint32_t ms,
                     const char* result, const char* reason) {
  if (!sdOk) return;
  bool fresh = !SD.exists("/log/trials.csv");
  File f = SD.open("/log/trials.csv", FILE_APPEND);
  if (!f) return;
  if (fresh) f.println("uptime_ms,bucket,intensity,duty,ms,result,reason");
  f.printf("%lu,%s,%.3f,%lu,%lu,%s,%s\n", (unsigned long)millis(), clean(bucket).c_str(),
           inten, (unsigned long)duty, (unsigned long)ms, result, reason);
  f.close();
}

static void loadConfig() {
  File f = SD.open("/config.json", FILE_READ);
  if (!f) return;
  JsonDocument d;
  if (deserializeJson(d, f)) { f.close(); return; }
  f.close();
  if (d["max_duty"].is<float>()) {
    float m = d["max_duty"].as<float>();
    if (m > 0.0f && m < maxDuty) maxDuty = m;   // config may only lower
  }
  if (d["wifi_ssid"].is<const char*>()) wifiSsid = d["wifi_ssid"].as<String>();
  if (d["wifi_password"].is<const char*>()) wifiPass = d["wifi_password"].as<String>();
  if (d["device_name"].is<const char*>()) deviceName = d["device_name"].as<String>();
}

static String reply(JsonDocument& d) { String s; serializeJson(d, s); return s; }
static String fail(const char* reason) {
  JsonDocument d; d["ok"] = false; d["reason"] = reason; return reply(d);
}

static String handleStim(JsonDocument& in) {
  if (!in["bucket"].is<const char*>() || !in["intensity"].is<float>() || !in["ms"].is<long>())
    return fail("bad_args");
  String bucket = in["bucket"].as<String>();
  float inten = in["intensity"].as<float>();
  long msReq = in["ms"].as<long>();
  inten = clampIntensity(inten);
  uint32_t ms = clampMs(msReq);
  uint32_t duty = dutyCounts(inten, maxDuty);

  const char* why = nullptr;
  uint32_t now = millis();
  if (estopLatched) why = "estop";
  else if (!armed) why = "not_armed";
  else if (stimActive) why = "busy";
  else if (everStimmed && (uint32_t)(now - lastEnd) < COOLDOWN_MS) why = "cooldown";
  else if (stimsLastHour() >= MAX_STIMS_PER_HOUR) why = "hourly_limit";

  if (why) {
    logTrial(bucket, inten, duty, ms, "refused", why);
    return fail(why);
  }
  recordStim();
  everStimmed = true;
  logTrial(bucket, inten, duty, ms, "accepted", "");   // log before ramp starts
  stimPeak = duty; stimDur = ms; stimStart = millis(); stimActive = true;
  JsonDocument d;
  d["ok"] = true; d["duty"] = duty; d["ms"] = ms; d["intensity"] = inten;
  return reply(d);
}

static String handleCmd(const String& line) {
  JsonDocument in;
  if (deserializeJson(in, line) || !in.is<JsonObject>() || !in["cmd"].is<const char*>())
    return fail("parse");
  String cmd = in["cmd"].as<String>();
  if (cmd == "status") {
    JsonDocument d;
    d["ok"] = true;
    d["chip"] = ESP.getChipModel();
    d["device_name"] = deviceName;
    d["uptime_ms"] = millis();
    d["armed"] = armed;
    d["sd"] = sdOk;
    d["max_duty"] = maxDuty;
    d["stims_last_hour"] = stimsLastHour();
    if (everStimmed) d["last_stim_ms_ago"] = (uint32_t)(millis() - lastEnd);
    else d["last_stim_ms_ago"] = nullptr;
    d["estop"] = estopLatched;
    d["active"] = stimActive;
    d["wifi_ip"] = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("");
    return reply(d);
  }
  if (cmd == "arm") {
    if (estopLatched) return fail("estop");
    armed = true; armedAt = millis();
    JsonDocument d; d["ok"] = true; d["armed"] = true; d["expires_ms"] = ARM_TIMEOUT_MS;
    return reply(d);
  }
  if (cmd == "disarm") {
    armed = false;
    JsonDocument d; d["ok"] = true; d["armed"] = false; return reply(d);
  }
  if (cmd == "stop") {
    endStim();
    JsonDocument d; d["ok"] = true; return reply(d);
  }
  if (cmd == "stim") return handleStim(in);
  return fail("unknown_cmd");
}

// Called every loop pass: E-stop, arm expiry, ramp.
static void tick() {
  bool low = digitalRead(PIN_ESTOP) == LOW;
  if (low) {
    estopLatched = true;
    armed = false;
    endStim();
    outDuty(0);
    return;
  }
  estopLatched = false;
  if (armed && (uint32_t)(millis() - armedAt) >= ARM_TIMEOUT_MS) armed = false;
  if (stimActive) {
    uint32_t t = millis() - stimStart;
    if (t >= stimDur) endStim();
    else outDuty(rampDuty(t, stimDur, stimPeak));
  }
}

static void pollSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      String line = serialBuf; serialBuf = "";
      line.trim();
      bool ov = serialOverflow; serialOverflow = false;
      if (ov) { Serial.println(fail("parse")); continue; }
      if (line.length() == 0) continue;
      Serial.println(handleCmd(line));
    } else if (c != '\r') {
      if (serialBuf.length() < 512) serialBuf += c; else serialOverflow = true;
    }
    tick();
  }
}

static void startWifiServer() {
  if (serverStarted || WiFi.status() != WL_CONNECTED) return;
  server.on("/cmd", HTTP_POST, []() {
    server.send(200, "application/json", handleCmd(server.arg("plain")));
  });
  server.begin();
  serverStarted = true;
}

void setup() {
  pinMode(PIN_PWM, OUTPUT);
  digitalWrite(PIN_PWM, LOW);                 // 0 before anything else
  pinMode(PIN_ESTOP, INPUT_PULLUP);
  ledcAttach(PIN_PWM, PWM_FREQ_HZ, PWM_BITS);
  outDuty(0);
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);                   // never block if no host is reading

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CS);
  sdOk = SD.begin(PIN_CS, SPI, 4000000);
  if (sdOk) { SD.mkdir("/log"); loadConfig(); }

  if (wifiSsid.length()) {                    // async join; serial stays live
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(deviceName.c_str());
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  }
}

void loop() {
  tick();
  pollSerial();
  if (wifiSsid.length()) {
    startWifiServer();
    if (serverStarted) { tick(); server.handleClient(); }
  }
  tick();
  delay(1);
}
