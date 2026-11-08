# Testing: what I tested, how, and what it measured

> **DANGER. Everything on a person here carries the risks in [SAFETY.md](SAFETY.md).** The dummy-load tests come first, and every one of them had nobody attached.

Dates are 2026. Raw logs are in [`gvs/bench_log.md`](../gvs/bench_log.md) and [`gvs/DEBUG.md`](../gvs/DEBUG.md). The commands are in [BUILD.md](BUILD.md).

## Status

**The builder reports (2026-11-08) that the whole chain works end to end:** traffic from the devices reaches the UNO Q, an enrolled category matches, and the headband fires. The footage of a friend steering the wearer from their phone is on the website's [HVAC page](https://aryagarg23.com/futures/hvac). The other READMEs in this repo (`pipeline/`, `uno_q/`, `tribe/`) were written earlier and have "not verified" lists that predate that. They were not re-run for this document.

What is checked by an automated test in this repo: the pipeline and the dashboard (97 tests), the UNO Q's msgpack encoder (3 tests), and the board layout (`gvs/board/check.py`). Everything else below was checked by hand, and is a measurement, not a test you can re-run from CI.

## 1. Before power

| Test | How | Result |
|---|---|---|
| Layout check | `python3 gvs/board/check.py` | `no placement errors`. It checks every net on the perfboard and flags double-used holes and anything under the XIAO |
| SPICE simulation | `python3 gvs/board/run2.py` (ngspice) | 0 mA idle. 1.00 and 2.00 mA exact into 2.2 kΩ. A shorted Q2 shows up in the readback. Results as recorded in `gvs/HANDOFF.md`. Not re-run on the Mac, where ngspice isn't installed |
| Continuity | meter, board off, battery feed wire not fitted | HV bus ↔ GND bus 9.16 kΩ (expected 9.15 kΩ). XIAO GND ↔ GND bus beeps. 5V ↔ GND doesn't. Relay − pins ↔ GND beep, + pins don't |

## 2. Bench: dummy load, nobody attached (2026-11-07)

Pulses are driven over USB serial by `gvs/tools/bench.py` (`status`, `idle`, `power`, `boost-sweep`, `boostpct`, `pulse`, `limits`), and each prints PASS or FAIL. A 2.2 kΩ load across the electrode leads, a meter across it (true mA = volts ÷ 2.2).

**Power.** With the battery feed wire fitted, HV at idle reads 3.85 to 3.89 V.

**Boost sweep, leads open.** HV by duty:

| Duty | 5% | 10% | 15% | 20% | 25% | 30% | 35% | 40% | 45% |
|---|---|---|---|---|---|---|---|---|---|
| HV (V) | 5.9 | 7.9 | 10.0 | 12.1 | 14.1 | 16.0 | 17.7 | 19.4 | 21.1 |

45% is the firmware ceiling and is now `BOOST_PCT`. During 3 s pulses with the leads open, HV peaked at 23 to 26.5 V (the cutoff is 28 V). Once the boost stops, HV bleeds back to about 3.9 V in about a second.

**Relays, leads open, 0.5 Hz sine.** The state went −1 → 0 → 1 → −1 → 0 → −1: it alternated and passed through "released" at every flip.

**Current into 2.2 kΩ, DC, 3 s:**

| Commanded | Meter | True current | Board's reading before calibration | HV during the pulse |
|---|---|---|---|---|
| 0.5 mA | 1.07 V | 0.486 mA | 0.69 to 0.72 | 21 V |
| 1.0 mA | 2.2 V | 1.00 mA | 1.13 to 1.14 | 19.5 V |
| 2.0 mA | 4.308 V | 1.958 mA | 1.92 to 2.03 | 17.0 V |

The output was right and the board's reading was off: at 0 mA commanded it read 0.25 to 0.28 mA. The fit `raw = 0.27 + 0.88 × true` is now applied in the firmware (`meas_ma`). The overcurrent trip still uses the uncorrected reading, which runs at or above the true current up to about 2.25 mA.

**Limits** (`bench.py limits`): `ma=5` clamps to 2.0. A 10 s request stops at 3 s. A second pulse inside 5 s is refused. `stop`, the kill switch and reset all give 0 V.

## 3. Firmware bring-up finds

| Date | What I found | Result |
|---|---|---|
| 11-07 | At 12 and 11 bits the LEDC PWM failed to attach (`requested frequency 20000 and duty resolution 12 can not be achieved`). The set and boost PWMs never ran, so every `/pulse` would have commanded 0 mA and reported success | PWM is 10-bit. The firmware faults at boot if either PWM fails to attach |
| 11-08 | Flat battery overnight. With no SSID the firmware kept an always-on hotspot beside BLE and flattened the 250 mAh cell. Idle HV read 2.48 V (3.75 to 3.88 V the night before) and the pulse log was cleared | With no SSID, WiFi stays off and the HTTP server does not start. The first fix crashed in `xQueueSemaphoreTake` because `WebServer` touched lwIP with WiFi off |

## 4. First on-head session (2026-11-07, BLE, USB unplugged, Mac on battery)

One person, pads on the mastoids. The kill switch had been removed and the plan was to pull a pad. (Don't.)

| Time | Pulse | Felt |
|---|---|---|
| 22:48 | 0.5 mA, 1 Hz sine, 2 s | tingle |
| 22:49 | 0.75 mA | tingle |
| 22:49 | 1.0 mA | more tingle |
| 22:53 to 22:58 | DC 3 s at 1.0, 1.0, 1.25, 1.5, 1.5 mA, alternating sides | minor tingle |
| 23:04 | 1.0 mA DC (a wire now cut into the pad's carbon layer) | stronger tingle |
| 23:12 | 1.0 mA DC (pads moved per the diagram) | hurts a little, unusual |
| 23:13 | 1.25 mA DC | no balance change |
| 23:15 | 1.5 mA DC | hurts, on top of the skin. Session stopped |

The board held the commanded current on every pulse and there were no faults. There was no vestibular effect at any level. The likely cause is the electrode connection: a bare wire in a 2 mm socket touches only a few points of the pad, which gives skin sensation and then pain without enough current reaching the vestibular nerve. [`gvs/DEBUG.md`](../gvs/DEBUG.md) lists the checks in order, cheapest first, with four meter-only tests:

| # | Check | Pass |
|---|---|---|
| A | fresh pads gel to gel, ohms between the two electrode wires, wiggle each pin | under about 1 kΩ and steady |
| B | meter across the two pad wires during a 1.0 mA, 3 s DC pulse | 1 to 5 V (1 to 5 kΩ). Over 10 V means poor contact |
| C | **true current:** meter across the 2.2 kΩ top resistor during the same pulse | 2.2 V (1.0 mA). Lower means the board is overstating the current |
| D | HV to GND during the pulse | stays above head volts + 3.3 V per mA + 0.2 V |

C is the one the board can't do for itself. I have not recorded these four on a head in this log.

## 5. Live mode and the Mac relay (2026-11-08)

Checked over USB serial at 0.3 mA, open leads (not metered):

- streaming +0.3 holds 0.3 mA on relay 1
- going silent reaches idle in 0.51 s ("live: controller silent, ramped off")
- −0.3 mA moves to relay 2
- −9 mA is clamped
- `stop` goes to idle

The Mac's Bluetooth relay (`gvs/tools/ble_bridge.py`) refuses any current while the Mac is on its charger and the board is on USB. Checked: `403 refused` for both `/live` and `/cmd pulse`. **A miss:** the serial checks above ran before that check was added, with the Mac on AC and USB in.

Live mode's limits have changed since: now 2.0 mA, a 1 s dead-man in the firmware (1.5 s of page silence on the UNO Q), and 30 minutes of current per rolling hour. The 60 s session cap is gone.

## 6. The software (automated)

```bash
cd pipeline
python3 -m venv .venv && .venv/bin/pip install pytest hypothesis
.venv/bin/python -m pytest -q          # 97 passed on 2026-11-08
```

| File | What it pins |
|---|---|
| `test_capture_contract.py` | the column order of `uno_q/linux/capture.sh` matches `packets.py` |
| `test_pipeline.py` | packet parsing round trips and never raises; service names; the classifier's intensity bounds; one-shot enrollment through the command line |
| `test_sliding.py` | 3 s windows slide every 1 s; the first stimulus on synthetic reels lands within 4 s; the refractory period covers the slowest pulse |
| `test_reels_vs_dms.py` | Instagram Reels and DMs share `cdninstagram.com`, so the domain alone can't decide; weight never breaks a tie; a photo opened in a DM goes to the DM bucket |
| `test_gvs_link.py` | whole-cycle sine bursts; the current is rounded down and never above `--max-ma`; a latched fault or bad token halts the link; busy, cooldown and hourly-limit refusals are skips; the relay and the mains refusal |
| `test_tribe.py`, `test_tribe_live.py` | TRIBE can lower a bucket's weight and never raise it; the live feed attributes scores to the right bucket |
| `test_rules.py` | a service rule fires an unenrolled service or vetoes an enrolled one; the rate floor still applies; weights stay in [0, 1]; a refused edit changes nothing; **pause** decides but never fires; the dashboard API, and the key lock off localhost |

The UNO Q's msgpack encoder is checked against a reference decoder: `python3 -m pytest uno_q/fun/test_fun_msgpack.py` (3 tests).

All pipeline tests use synthetic traffic. The traffic-fingerprinting limits (the shared Instagram CDN, QUIC multiplexing, prefetching) are in [`research/traffic_fingerprinting.md`](../research/traffic_fingerprinting.md).

## 7. On the UNO Q (2026-11-08)

Dashboard and pipeline run on the board in demo mode (synthetic traffic made on the board):

| Check | Result |
|---|---|
| `/api/state` without the key | 401 |
| `/api/state` with the key | 200 |
| a rule POSTed with the key | saved to `store/rules.json` on the board |
| that rule | fired every 10 s at its weight (50%, 1250 ms), shown as 15, 25, 35 s ago |

The board's clock was about 14 months behind (no internet), so the page measures ages on the board's clock (`server_time`). With the Mac's own en0 traffic streamed in over USB, the dashboard listed real services (anthropic.com and others) while firing nothing, because no current had been given.

## 8. Not covered by anything here

- No measurement of head and electrode resistance, and checks A to D above, are recorded.
- The `D0` strapping-pin constraint in `gvs/DEBUG.md` is from memory, not the datasheet.
- The headroom table in [HARDWARE.md](HARDWARE.md) is arithmetic from the measured supply, not measured on a head.
- No test checks the firmware's code paths with a failing component (a shorted Q2, a stuck relay). The readback trip is described and was checked with the sink working.
- Nothing certifies the device for use on people.
