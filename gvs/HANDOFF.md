# GVS zapper — handoff (MakeUC 2026)

Read this first. It is the state of the build as of Sat 7 Nov 2026, ~9:45 pm.

## What this is
DIY galvanic vestibular stimulation (GVS) device for self-applied aversive conditioning:
tailnet traffic gets classified, and the device gives a small current pulse behind the ears
for disliked content. Hardware is built; **firmware has never been compiled or flashed.**

## Hardware (as built)
Board: Particle FeatherWing Tripler perfboard. XIAO ESP32-C3 in the middle section, USB pointing right.
Powered by a 3.7 V 250 mAh LiPo soldered permanently to the XIAO BAT pads.

- **Section 1 (top), boost converter:** D10 → 330Ω → 2N3904 (Q1) switching a 1mH inductor,
  1N5819 diode into 47µF on the HV bus (col 4). Bleed 10k HV→GND. HV sense divider
  100k/8.2k → D2. Target HV 20–24 V. Firmware hard cutoff at 28 V.
- **Section 2 (middle), current sink:** 2N3904 (Q2) with 1k+100Ω (1.1k) emitter resistor.
  I = V_SET / 1100. Readback SENSE → 100k/100k divider → D1. TOP = HV through 2.2k.
- **Section 3 (bottom):** LM358 driving the sink (pin 8 on HV). SET comes from D3 PWM
  through a 10k + 1µF filter. 104 = HV decoupling cap.
- **Relays:** 2× Tongling JQC-3FF-S-Z **5V** relay modules, pins S/+/− (top to bottom),
  plugged in at col 20.
  - Relay 1: S = D4. Relay 2: S = D5. − = GND.
  - + pins are linked to each other by a black wire (S1 C19 ↔ S3 C19).
  - NO → TOP (S2 B1, C1). NC → BOTTOM (S2 E8, E10). COM → electrodes.
  - Relay 1 COM goes through the kill switch to the left electrode; relay 2 COM goes to the right electrode.
- Exact hole-by-hole layout: `board/layout.py` (v6, matches what was soldered).
  - `board/check.py` checks every net.
  - `board/sim.py` + `run2.py` run the ngspice simulation.
  - Results: 0 mA idle; 1.00 / 2.00 mA exact into 2.2k; a shorted Q2 shows up in the readback.

### Differences from the original plan (already in layout.py)
- S1 transistor area shifted one column right. Extra insulated jumper S1 D7 → D4 (diode to HV).
- D2 jumper lands in S1 A12, so the sense bridge runs A9–A12.
- Bleed 10k goes from the col 4 bottom header hole to S1 D6 (HV bus to GND bus directly).
- Relay 2 GND jumper goes S3 E20 → col 17 bottom pair inner (XIAO GND), not across the chip.
- S3 1k resistors may be lying flat (cols 14→18?) instead of standing. Not confirmed from a back photo yet.

## Tests passed (battery-feed wire NOT yet connected)
- HV bus ↔ GND bus = **9.16 kΩ** (expected 9.15k). The bleed and the sense divider are both in.
- XIAO GND ↔ GND bus: beep. XIAO 5V ↔ GND: no beep.
- Relay − pins ↔ GND: beep. Relay + pins ↔ GND: no beep.

## Open items / next steps (in order)
1. **Relay LEDs are both ON right now.** Figure out whether that's the module's power LED
   (normal once + has power) or the relays actually energized (a click; the COM↔NO terminals beep).
   - If they're energized at idle with our firmware running: set `RELAY_ACTIVE_LOW = true`.
   - Before flashing, the old sketch on the XIAO may be driving D4/D5, so don't judge until after the flash.
   - No electrodes attached, so this is harmless for now.
2. **Flash the firmware** (`firmware/gvs_controller/gvs_controller.ino`).
   - Board: Seeed XIAO ESP32-C3 (FQBN `esp32:esp32:XIAO_ESP32C3`). Board URL:
     `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
   - arduino-cli route:
     ```
     brew install arduino-cli
     arduino-cli config init
     arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
     arduino-cli core update-index && arduino-cli core install esp32:esp32
     arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C3 firmware/gvs_controller
     arduino-cli upload -p /dev/cu.usbmodem* --fqbn esp32:esp32:XIAO_ESP32C3 firmware/gvs_controller
     arduino-cli monitor -p /dev/cu.usbmodem* -c baudrate=115200
     ```
   - Never compiled before: expect small fixes. It has `#if` guards for esp32 core 2.x vs 3.x
     (LEDC and watchdog APIs differ).
   - WiFi: set `WIFI_SSID` / `WIFI_PASS`. If the board can't join within 10 s it makes its own
     hotspot, **GVS-zapper / zapzap123**, at http://192.168.4.1/.
   - Change `TOKEN` (default "change-me"). /pulse, /boost and /stop need `?token=`.
   - Keep `BOOST_PCT = 0` for the first flash.
3. **Battery feed wire:** from XIAO BAT+ (or the battery red lead) to **S1 D19**.
   - Do it only after flashing. Optionally put a switch in it as an "arm" switch.
   - D19 sits next to relay 1's − pin (GND): keep the solder small.
   - Check afterwards: D19 ↔ GND bus must not beep.
   - Powered up, HV should read about 3.5–3.9 V (battery through the diode).
4. **Relay click test** (no electrodes): `/pulse?ma=0.5&mode=sine&hz=0.5&ms=3000&token=…`
   - The relays should alternate.
   - The 5V coils run on 3.7–4.2 V, so a low battery may not pull them in.
5. **Boost tuning** (no electrodes): `/boost?pct=5&token=…`, stepping up 5% at a time.
   - Stop at HV 20–24 V on a full battery. Never above 28 V.
   - Check Q1, the inductor and the diode for heat.
   - Write the result into `BOOST_PCT`, reflash, then send `/boost?pct=0`.
6. **Dummy load tests** with a 2.2k across the electrode leads (V ÷ 2.2 = mA):
   - idle 0 V; 1 mA DC ≈ 2.2 V; 2 mA ≈ 4.4 V
   - `pol=1` flips the sign; sine swings ±
   - ma=5 clamps to 2; ms=10000 stops at 3 s; the cooldown refuses a second pulse
   - `/stop`, the kill switch and the reset button all give 0 V
   - a 4.7k load gives about 1.6 mA (compliance limit; `/status` still says 2)
7. Then wire the classifier → `/pulse` calls.

## Firmware facts
- Pins: D3 = SET PWM (20 kHz, 12-bit), D4/D5 = relays, D1 = current readback (×2 divider),
  D10 = boost PWM, D2 = HV sense (÷13.2).
- Limits: FW_MAX_MA 2.0, MAX_MS 3000, COOLDOWN_MS 5000, RAMP_MS 300, MAX_HZ 2,
  BOOST_MAX_PCT 45, HV_MAX 28 (3 readings in a row → kill).
- Watchdog 2 s. Polarity flips always pass through zero current.
- Readback trips on overcurrent (>2.3 mA) or a mismatch with the command.
- Endpoints: `/pulse` (ma, ms, mode=sine|dc, pol, hz, token), `/stop`, `/status` (JSON incl. hv, boost_pct), `/boost?pct=`.

## Safety rules (non-negotiable)
- Never wear the electrodes while the laptop is on its charger or the board is on wall power.
- Do every dummy-load test before the first human test.
- Electrodes behind the ears only, seated, kill switch in hand.
- Start at 0.5 mA / 1 s and go up in 0.25 mA steps, max 2 mA.
- Stop on flashes of light, burning, nausea or a headache.
- Not for anyone with epilepsy, implants or balance disorders.

## Files
- `build_guide.html`: solder checklist with section pictures (open in a browser).
- `pictures/`
  - `S1/S2/S3_front/back.png`: one front and one back picture per section.
  - `full_front.png`: every wire on one picture.
  - `test_points.png`: all 21 meter checks.
  - `probe_steps.png`: the simple beep tests.
- `board/`: layout + net check + SPICE sim + drawing scripts (Python 3, ngspice, cairosvg).
