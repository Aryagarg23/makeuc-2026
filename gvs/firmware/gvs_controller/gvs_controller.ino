// GVS stimulator controller -- Seeed XIAO ESP32-C3 (board: "XIAO_ESP32C3")
// C3 has no DAC: 20 kHz 10-bit PWM on D3, smoothed by the 10k/1uF RC into the LM358.
// PWM duty 0 = a true 0 V, so idle is exactly zero.
//
// Power: 3.7 V LiPo on the XIAO's BAT+/BAT- pads; the BAT rail feeds relays + boost.
// DIY boost: D10 -> 330R -> 2N3904 switching a 1mH inductor, 1N5819 -> 47uF, 10k bleed.
// Fixed duty (BOOST_PCT), HV readback on D2 via 100k/8.2k, hard cutoff at HV_MAX.
// The boost only runs DURING a pulse (saves battery; no high voltage at idle).
// Tune on the bench with /boost?pct=N (battery freshly charged) while measuring HV.
//
// Hardware (see wiring notes): LM358 + 2N3904 current sink, I = V_SET / 1100 ohm
// (hardware ceiling ~3.0 mA at 100% duty), two SPDT relays for polarity.
// Current readback: SENSE -> 100k -> D1 -> 100k -> GND (C3 ADC tops out ~2.5 V).
// Relays de-energised = both electrodes on the same node = NO current path.
//
// HTTP API (all need ?token=...):
//   /pulse?ma=1.0&ms=2000&mode=sine|dc&pol=0|1&hz=1.0
//   /stop
//   /status
//   /boost?pct=12   bench tuning: holds the boost on at N% (clamped to BOOST_MAX_PCT)
//   /boost?pct=0    ends tuning (boost goes back to pulse-only)
// USB serial (115200): the same commands for the bench, see handleSerial().
// A fault latches until power cycle.

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <esp_task_wdt.h>

// ---------- config ----------
// WIFI_SSID, WIFI_PASS, TOKEN, AP_PASS live in secrets.h (git-ignored; copy secrets.example.h).
#include "secrets.h"

const int  PIN_PWM    = D3;     // GPIO5 -> 100k to GND, -> 10k -> SET node
const int  PIN_RELAY1 = D4;     // GPIO6, relay 1 (electrode L)
const int  PIN_RELAY2 = D5;     // GPIO7, relay 2 (electrode R)
const int  PIN_ISENSE = D1;     // GPIO3, ADC1 (D3/GPIO5 is ADC2: unusable with WiFi)
const float ISENSE_DIV = 2.0f;  // 100k/100k divider
const int  PWM_FREQ   = 20000;
const int  PWM_BITS   = 10;     // C3 LEDC clock here is 40 MHz: 20 kHz x 2^bits must fit, so 11 and 12 bits fail to attach (boot log 2026-11-07)
const int  PWM_MAX    = (1 << PWM_BITS) - 1;
const int  PWM_CH     = 0;      // only used on Arduino-ESP32 core 2.x
const bool RELAY_ACTIVE_LOW = false;  // your modules: HIGH = on (red one: jumper on H)

// ---- boost converter ----
const int   PIN_BOOST     = D10;    // GPIO10 -> 330R -> 2N3904 base (10k base->GND)
const int   PIN_HVSENSE   = D2;     // GPIO4, ADC1: HV -> 100k -> D2 -> 8.2k -> GND
const float HV_DIV        = 108.2f / 8.2f;
const int   BOOST_CH      = 2;      // core 2.x only (different timer from PWM_CH)
float       BOOST_PCT     = 45;     // bench 2026-11-07: 45% -> ~21-23 V open, 17 V at 2 mA into 2.2k (gvs/bench_log.md)
const float BOOST_MAX_PCT = 45;     // /boost can never go above this (sim: <27 V worst case)
const float HV_MAX        = 28.0f;  // above this: boost off, stim off, fault
const float HV_READY      = 12.0f;  // pulse waits until HV reaches this
const uint32_t HV_WAIT_MS = 1500;   // ...or gives up

const float    R_SENSE      = 1100.0f; // ohms (1k + 100R)
const float    FW_MAX_MA    = 2.0f;    // firmware ceiling; hardware ceiling ~3.0 mA
const uint32_t MAX_MS       = 3000;    // longest single pulse
const uint32_t COOLDOWN_MS  = 5000;    // min gap between pulses
const int      MAX_PER_HOUR = 30;      // research/gvs.md §6: <= 60-90 s of stimulus per hour, far below nausea protocols
const uint32_t RAMP_MS      = 300;     // soft start/stop, avoids the "zap"
const float    MAX_HZ       = 2.0f;
const float    OVER_TOL_MA  = 0.4f;    // trip if measured > commanded + this
const uint32_t OVER_TRIP_MS = 50;

// ---------- state ----------
WebServer server(80);
enum Mode { IDLE, DC, SINE };
Mode     mode = IDLE;
float    targetMa = 0, freqHz = 1.0f, commandedMa = 0;
int      polarity = 0;          // 0: L->R, 1: R->L
int      relayState = -1;       // -1 disconnected, 0/1 polarity
uint32_t tStart = 0, durMs = 0, lastEnd = 0, overSince = 0;
int      flipStage = 0; uint32_t flipT = 0;
bool     faulted = false; String faultMsg = "", lastMsg = "";
bool     waitingHV = false; uint32_t hvT0 = 0;
uint32_t pulseLog[MAX_PER_HOUR]; int pulseCount = 0, pulseHead = 0;  // ring of accepted pulse start times

bool hourFull(uint32_t now) {        // the oldest of the last MAX_PER_HOUR pulses is under an hour old
  return pulseCount >= MAX_PER_HOUR && now - pulseLog[pulseHead] < 3600000UL;
}
void logPulse(uint32_t now) {
  pulseLog[pulseHead] = now; pulseHead = (pulseHead + 1) % MAX_PER_HOUR;
  if (pulseCount < MAX_PER_HOUR) pulseCount++;
}

// ---------- low level ----------
void relayWrite(int pin, bool on) {
  if (RELAY_ACTIVE_LOW) {
    // 3.3V HIGH can leave a 5V opto module half-on, so float the pin for "off"
    if (on) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); }
    else    { pinMode(pin, INPUT); }
  } else {
    pinMode(pin, OUTPUT); digitalWrite(pin, on ? HIGH : LOW);
  }
}

// -1 = both NC (both electrodes on BOTTOM node: disconnected)
//  0 = relay1 on: L -> TOP, R -> BOTTOM  (current L -> R)
//  1 = relay2 on: R -> TOP, L -> BOTTOM  (current R -> L)
void setRelays(int s) {
  relayWrite(PIN_RELAY1, s == 0);
  relayWrite(PIN_RELAY2, s == 1);
  relayState = s;
}

bool pwmSetup() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  return ledcAttach(PIN_PWM, PWM_FREQ, PWM_BITS);
#else
  if (!ledcSetup(PWM_CH, PWM_FREQ, PWM_BITS)) return false;
  ledcAttachPin(PIN_PWM, PWM_CH);
  return true;
#endif
}

void pwmWrite(int duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_PWM, duty);
#else
  ledcWrite(PWM_CH, duty);
#endif
}

bool boostSetup() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  return ledcAttach(PIN_BOOST, PWM_FREQ, PWM_BITS);
#else
  if (!ledcSetup(BOOST_CH, PWM_FREQ, PWM_BITS)) return false;
  ledcAttachPin(PIN_BOOST, BOOST_CH);
  return true;
#endif
}

bool boostTuning = false;

void boostWritePct(float pct) {
  pct = constrain(pct, 0.0f, BOOST_MAX_PCT);
  int duty = (int)roundf(pct / 100.0f * PWM_MAX);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_BOOST, duty);
#else
  ledcWrite(BOOST_CH, duty);
#endif
}

float hvVolts() {
  return analogReadMilliVolts(PIN_HVSENSE) * HV_DIV / 1000.0f;
}

void setCurrentMa(float ma) {
  if (ma < 0) ma = 0;
  if (ma > FW_MAX_MA) ma = FW_MAX_MA;
  commandedMa = ma;
  int duty = (int)roundf(ma * R_SENSE / 3300.0f * PWM_MAX);
  pwmWrite(constrain(duty, 0, PWM_MAX));
}

// Raw readback reads high: bench 2026-11-07 against a meter on 2.2k gave raw = 0.27 + 0.88 x true
// (true 0.49 -> 0.70, 1.00 -> 1.14, 1.96 -> 2.00; gvs/bench_log.md). raw >= true below ~2.25 mA.
const float ISENSE_OFS_MA = 0.27f, ISENSE_GAIN = 0.88f;

float rawMa() {                      // mV / ohm = mA, uncorrected
  return analogReadMilliVolts(PIN_ISENSE) * ISENSE_DIV / R_SENSE;
}

float measuredMa() {                 // calibrated estimate of the true current
  float m = (rawMa() - ISENSE_OFS_MA) / ISENSE_GAIN;
  return m < 0 ? 0 : m;
}

void outputOff() {
  pwmWrite(0);                       // 0% duty = solid 0 V
  commandedMa = 0;
  setRelays(-1);
  if (!boostTuning) boostWritePct(0); // HV bleeds down through the 10k
  waitingHV = false;
  mode = IDLE; flipStage = 0; overSince = 0;
  lastEnd = millis();
}

void kill(const String& why) {
  outputOff();
  boostTuning = false; boostWritePct(0);
  faulted = true; faultMsg = why;
  Serial.println("FAULT: " + why);
}

// Polarity change: ramp to 0, wait, disconnect, wait, reconnect, wait.
// Returns true while the flip is in progress.
bool handleFlip(int want, uint32_t now) {
  if (want == relayState && flipStage == 0) return false;
  setCurrentMa(0);
  switch (flipStage) {
    case 0: flipStage = 1; flipT = now + 30; break;
    case 1: if (now >= flipT) { setRelays(-1);   flipStage = 2; flipT = now + 15; } break;
    case 2: if (now >= flipT) { setRelays(want); flipStage = 3; flipT = now + 20; } break;
    case 3: if (now >= flipT) { flipStage = 0; return false; } break;
  }
  return true;
}

void checkReadback(uint32_t now) {
  // Hard limit on the RAW reading: it reads at or above the true current in the working range, so it trips early, not late.
  float raw = rawMa();
  if (raw > FW_MAX_MA + 0.3f) { kill("overcurrent raw " + String(raw, 2) + " mA"); return; }
  // Tracking check on the calibrated value: the raw +0.27 mA offset sat within 0.02 mA of OVER_TOL_MA in sine troughs.
  float m = measuredMa();
  if (m > commandedMa + OVER_TOL_MA) {
    if (!overSince) overSince = now;
    else if (now - overSince > OVER_TRIP_MS)
      kill("readback " + String(m, 2) + " mA vs cmd " + String(commandedMa, 2));
  } else overSince = 0;
}

// ---------- HTTP ----------
bool authed() {
  if (server.arg("token") != TOKEN) { server.send(403, "text/plain", "bad token\n"); return false; }
  return true;
}

// Shared by HTTP and USB serial. Returns an HTTP status; msg is the reply body.
int startPulse(float ma, long ms, float hz, int pol, bool dc, String& msg) {
  if (faulted)       { msg = "faulted: " + faultMsg + " (power cycle)"; return 423; }
  if (mode != IDLE)  { msg = "busy"; return 409; }
  if (boostTuning)   { msg = "boost tuning on; boost 0 first"; return 409; }
  if (BOOST_PCT <= 0){ msg = "BOOST_PCT not set yet"; return 409; }
  if (lastEnd && millis() - lastEnd < COOLDOWN_MS) { msg = "cooldown"; return 429; }
  if (hourFull(millis())) { msg = "hourly_limit"; return 429; }

  targetMa = constrain(ma, 0.0f, FW_MAX_MA);
  durMs    = (uint32_t)constrain(ms, (long)(2 * RAMP_MS), (long)MAX_MS);
  freqHz   = constrain(hz, 0.2f, MAX_HZ);
  polarity = pol ? 1 : 0;
  mode     = dc ? DC : SINE;
  tStart   = millis();
  overSince = 0;
  waitingHV = true; hvT0 = millis();
  logPulse(hvT0);
  boostWritePct(BOOST_PCT);          // charge the HV rail, pulse starts once it's up
  msg = "ok " + String(targetMa, 2) + " mA " + String(durMs) + " ms";
  return 200;
}

int setBoost(float pct, String& msg) {
  if (faulted)      { msg = "faulted: " + faultMsg; return 423; }
  if (mode != IDLE) { msg = "busy"; return 409; }
  pct = constrain(pct, 0.0f, BOOST_MAX_PCT);
  boostTuning = pct > 0;
  boostWritePct(pct);
  delay(300);                        // let the output settle before reading
  msg = "boost " + String(pct, 1) + "% -> HV " + String(hvVolts(), 2) + " V (check with your meter)";
  return 200;
}

void handlePulse() {
  if (!authed()) return;
  String msg;
  int code = startPulse(server.hasArg("ma") ? server.arg("ma").toFloat() : 0.5f,
                        server.hasArg("ms") ? server.arg("ms").toInt() : 1500,
                        server.hasArg("hz") ? server.arg("hz").toFloat() : 1.0f,
                        server.arg("pol").toInt(),
                        server.arg("mode") == "dc", msg);
  server.send(code, "text/plain", msg + "\n");
}

void handleStop() {
  if (!authed()) return;
  outputOff();
  server.send(200, "text/plain", "stopped\n");
}

String statusJson() {
  uint32_t cd = (lastEnd && millis() - lastEnd < COOLDOWN_MS) ? COOLDOWN_MS - (millis() - lastEnd) : 0;
  String j = "{\"mode\":\"" + String(mode == IDLE ? "idle" : mode == DC ? "dc" : "sine") +
             "\",\"cmd_ma\":" + String(commandedMa, 3) +
             ",\"meas_ma\":" + String(measuredMa(), 3) +
             ",\"raw_ma\":" + String(rawMa(), 3) +
             ",\"relay\":" + String(relayState) +
             ",\"hv\":" + String(hvVolts(), 2) +
             ",\"boost_pct\":" + String(BOOST_PCT, 1) +
             ",\"cooldown_ms\":" + String(cd) +
             ",\"pulses_logged\":" + String(pulseCount) +
             ",\"hour_full\":" + String(hourFull(millis()) ? "true" : "false") +
             ",\"fault\":" + String(faulted ? "true" : "false") +
             ",\"msg\":\"" + (faulted ? faultMsg : lastMsg) + "\"}\n";
  return j;
}

void handleStatus() {
  if (!authed()) return;
  server.send(200, "application/json", statusJson());
}

// USB serial, for the bench. Same checks and limits as HTTP; replies "<code> <msg>".
//   status | stop | boost <pct> | boostpct <pct> | pulse <ma> <ms> <hz> <pol> <sine|dc>
// boostpct sets BOOST_PCT in RAM until reset (put the tuned value in the source to keep it).
// Never run pulses over USB while electrodes are on a person and the Mac is on its charger.
void handleSerial() {
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\n') { if (line.length() < 64) line += c; continue; }
    line.trim();
    String msg; int code = 400;
    char cmd[12] = {0}, md[8] = "sine"; float a = 0, hz = 1.0f; long ms = 0; int pol = 0;
    int n = sscanf(line.c_str(), "%11s %f %ld %f %d %7s", cmd, &a, &ms, &hz, &pol, md);
    String k(cmd);
    if (k == "status") { Serial.print(statusJson()); line = ""; continue; }
    else if (k == "stop") { outputOff(); code = 200; msg = "stopped"; }
    else if (k == "boost" && n >= 2) code = setBoost(a, msg);
    else if (k == "boostpct" && n >= 2) {
      if (mode != IDLE || boostTuning) { code = 409; msg = "busy"; }
      else { BOOST_PCT = constrain(a, 0.0f, BOOST_MAX_PCT); code = 200; msg = "BOOST_PCT " + String(BOOST_PCT, 1); }
    }
    else if (k == "pulse" && n >= 3) code = startPulse(a, ms, n >= 4 ? hz : 1.0f, n >= 5 ? pol : 0, String(md) == "dc", msg);
    else if (line.length()) msg = "status | stop | boost <pct> | boostpct <pct> | pulse <ma> <ms> <hz> <pol> <sine|dc>";
    else { line = ""; continue; }
    Serial.println(String(code) + " " + msg);
    line = "";
  }
}

void handleBoost() {
  if (!authed()) return;
  String msg;
  int code = setBoost(server.arg("pct").toFloat(), msg);
  server.send(code, "text/plain", msg + "\n");
}

// ---------- main ----------
void setup() {
  setRelays(-1);
  Serial.begin(115200);
  // A PWM that failed to attach ignores every write, so /pulse would report currents it never made.
  bool pwmOk = pwmSetup();
  pwmWrite(0);
  bool boostOk = boostSetup();
  boostWritePct(0);                  // off until a pulse (or tuning) asks for it
  if (!pwmOk || !boostOk) kill(String("ledc attach failed:") + (pwmOk ? "" : " SET") + (boostOk ? "" : " BOOST"));
  analogReadResolution(12);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nGVS ready at http://%s/  (gvs.local)\n", WiFi.localIP().toString().c_str());
  } else {
    // no known WiFi: make our own hotspot so testing never depends on venue WiFi
    WiFi.mode(WIFI_AP);
    WiFi.softAP("GVS-zapper", AP_PASS);
    Serial.printf("\nNo WiFi. Join hotspot GVS-zapper (password in secrets.h), then http://%s/\n", WiFi.softAPIP().toString().c_str());
  }
  MDNS.begin("gvs");

  server.on("/pulse",  handlePulse);
  server.on("/stop",   handleStop);
  server.on("/status", handleStatus);
  server.on("/boost",  handleBoost);
  server.begin();

  // watchdog: a hung loop resets the chip, which releases both relays
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg = { .timeout_ms = 2000, .idle_core_mask = 0, .trigger_panic = true };
  if (esp_task_wdt_reconfigure(&cfg) != ESP_OK) esp_task_wdt_init(&cfg);
#else
  esp_task_wdt_init(2, true);
#endif
  esp_task_wdt_add(NULL);
}

void loop() {
  esp_task_wdt_reset();
  server.handleClient();
  handleSerial();

  static int hvHigh = 0;             // 3 readings in a row, so one noisy sample can't trip it
  float hv = hvVolts();
  hvHigh = (hv > HV_MAX) ? hvHigh + 1 : 0;
  if (hvHigh >= 3 && !faulted) { kill("overvoltage " + String(hv, 1) + " V"); return; }

  if (mode == IDLE) return;

  uint32_t now = millis();
  if (waitingHV) {                   // boost is charging the 47uF
    if (hv >= HV_READY) { waitingHV = false; tStart = now; lastMsg = ""; }
    else if (now - hvT0 > HV_WAIT_MS) {
      outputOff();
      lastMsg = "boost only reached " + String(hv, 1) + " V; raise BOOST_PCT or charge battery";
    }
    return;
  }
  uint32_t t = now - tStart;
  if (t >= durMs) { outputOff(); return; }

  float env = 1.0f;                                  // trapezoid envelope
  if (t < RAMP_MS)               env = t / (float)RAMP_MS;
  else if (durMs - t < RAMP_MS)  env = (durMs - t) / (float)RAMP_MS;

  float ma; int want;
  if (mode == DC) {
    ma = targetMa * env; want = polarity;
  } else {
    float s = sinf(2.0f * PI * freqHz * t / 1000.0f);
    ma = fabsf(s) * targetMa * env;
    want = (s >= 0) ? polarity : 1 - polarity;       // relay flips at zero crossings
  }

  if (handleFlip(want, now)) return;
  setCurrentMa(ma);
  checkReadback(now);
}
