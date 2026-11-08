# gvs — the device

> **DANGER. This device passes current through your head and can cause permanent damage.** Read [`../docs/SAFETY.md`](../docs/SAFETY.md) first. The full documentation: [HARDWARE](../docs/HARDWARE.md) (circuit, parts, perfboard), [PINOUT](../docs/PINOUT.md), [BUILD](../docs/BUILD.md), [TESTING](../docs/TESTING.md), [SOFTWARE](../docs/SOFTWARE.md).

The device's design and wiring are documented in `HANDOFF.md`, including the original bench plan. This file records what changed after it was built, and what's next.

## Firmware state (flashed 2026-11-07 to the XIAO, MAC e8:f6:0a:14:37:c4)

**Build and flash:**
```bash
gvs/tools/make_secrets.sh [WIFI_SSID WIFI_PASS]   # once; writes secrets.h + device.env (both git-ignored)
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C3 gvs/firmware/gvs_controller
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32C3 gvs/firmware/gvs_controller
```

**Changes from the handoff firmware:**
- **PWM is 10-bit, not 12.**
  - The first flash logged `ledc: requested frequency 20000 and duty resolution 12 can not be achieved`. 11 bits failed the same way.
  - The current-set and boost PWMs never attached, so every `/pulse` would have produced 0 mA and reported success.
  - The firmware now faults at boot if either PWM fails to attach. 11-bit flash log: `FAULT: ledc attach failed: SET BOOST`.
  - 10 bits gives about 3 µA per step.
- **Secrets are out of the source.** `WIFI_SSID`, `WIFI_PASS`, `TOKEN` and `AP_PASS` live in `secrets.h`. The token and hotspot password are random. `device.env` holds `GVS_URL` and `GVS_TOKEN` for the pipeline.
- **30 pulses per hour**, enforced on the device. Pulse 31 gets `429 hourly_limit` (`research/gvs.md` §6).
- **USB serial bench commands**: `status`, `stop`, `boost <pct>`, `boostpct <pct>` and `pulse <ma> <ms> <hz> <pol> <sine|dc>`. They pass through the same checks and limits as HTTP (`startPulse`, `setBoost`), and `gvs/tools/bench.py` drives them. Never pulse over USB with electrodes on a person while the Mac is on its charger.

**Boot check after the last flash** (battery feed wire not connected, no WiFi credentials, so the board runs its `GVS-zapper` hotspot):
```
{"mode":"idle","cmd_ma":0.000,"meas_ma":0.027,"relay":-1,"hv":0.00,"boost_pct":0.0,"cooldown_ms":0,"pulses_logged":0,"hour_full":false,"fault":false,"msg":""}
```

**Hardware checks run here:** `python3 gvs/board/check.py` gives `no placement errors`. The SPICE sim (`board/sim.py`) wasn't re-run here because ngspice isn't installed.

## Next, in order (handoff steps 1, 3–6)

1. **Relay LEDs.** The firmware is now holding D4/D5 at "off". If a relay's LED is lit, check for a click or a COM↔NO beep. If either relay is actually energized at idle, set `RELAY_ACTIVE_LOW = true` and reflash.
2. **Battery feed wire.** Connect XIAO BAT+ to S1 D19. Then check that D19 ↔ GND does not beep. With power on, `status` should show `hv` around 3.5–3.9.
3. **WiFi.** Either join the Mac to `GVS-zapper` (password in `device.env`; the Mac loses internet while joined), or put your WiFi in `secrets.h` and reflash. The second option is needed for the pipeline and keeps the Mac online. `device.env`'s `GVS_URL` then becomes `http://gvs.local`.
4. **Relay click test, no electrodes.** `/pulse` refuses with "BOOST_PCT not set yet" until step 5, so tune the boost first and click-test after.
5. **Boost tuning, no electrodes.** `/boost?pct=5`, then step up 5% at a time to reach 20–24 V. Never go above 28 V. Feel Q1, the inductor and the diode for heat. Write the result into `BOOST_PCT`, reflash, then send `/boost?pct=0`.
6. **Dummy loads (`HANDOFF.md` step 6).** Use 2.2k, then 4.7k. Check that `/stop`, the kill switch and reset all bring the output to 0 V.

Then follow the on-head procedure in `research/gvs.md`: battery only, the Mac off its charger, seated, kill switch in hand, starting at 0.5 mA.

## Not done

- **Session limit:** `research/gvs.md` asks for 60 minutes per session; there is none.
- **Impedance check:** there is no check that refuses to stimulate above 10 kΩ. The 4.7k compliance limit (HANDOFF step 6) means a high-impedance contact gets less current than `/status` reports.
- **Readback at idle:** current readback runs only during a pulse. At idle both relays sit on NC, so the electrodes are on the same node.
- **Physically unverified:** whether the relay modules are active-high, the boost, and every analog path. Nothing has been powered beyond the XIAO's own battery pads.
