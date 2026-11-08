# Build and bring-up

> **DANGER. This device passes current through your head and can cause permanent damage.** Do the steps in order. Do not put an electrode on skin until every step through "Dummy loads" has passed, and read [SAFETY.md](SAFETY.md) first.

Parts and what the circuit does are in [HARDWARE.md](HARDWARE.md). The pins are in [PINOUT.md](PINOUT.md). What was tested, and what it measured, is in [TESTING.md](TESTING.md).

## 1. Solder the board

Build it from the pictures in `gvs/pictures/` and the hole-by-hole layout in `gvs/board/layout.py`. `gvs/build_guide.html` is a step-by-step guide made from the same layout.

1. Check the layout on paper first: `python3 gvs/board/check.py`. It must print `no placement errors`.
2. Solder section by section (S1 boost, S2 current sink and XIAO, S3 LM358 network), then the long jumpers J1 to J13, then the relay modules at column 20.
3. **Leave the battery feed wire off for now** (the black wire from the XIAO's BAT+ to S1 D19). Keep the LiPo's own connection to the XIAO's BAT pads, but do not close the feed to the board yet.
4. If you have ngspice, run the simulation of the layout: `python3 gvs/board/run2.py` (`sim.py` puts `/home/claude/perf` on `sys.path`; change that line on another machine). It builds the netlist from the same layout. Expect 0 mA idle, and 1.00 and 2.00 mA into 2.2 kΩ. It wasn't re-run on the Mac, where ngspice isn't installed.

## 2. Continuity, with the meter and no power

| Check | Expect |
|---|---|
| HV bus (col 4) ↔ GND bus (col 6) | about 9.15 kΩ (the 10k bleed in parallel with the sense divider). I read 9.16 kΩ |
| XIAO GND ↔ the GND bus | beep |
| XIAO 5V ↔ GND | no beep |
| each relay's − pin ↔ GND | beep |
| each relay's + pin ↔ GND | no beep |

If any of these fails, stop and find the fault. `gvs/pictures/test_points.png` and `probe_steps.png` show where to put the probes.

## 3. Firmware

Install the toolchain once:

```bash
brew install arduino-cli
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index && arduino-cli core install esp32:esp32
```

Make the secrets (a random token and hotspot password, written to two git-ignored files), then compile and flash:

```bash
gvs/tools/make_secrets.sh                      # or: make_secrets.sh WIFI_SSID WIFI_PASS
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C3 gvs/firmware/gvs_controller
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:XIAO_ESP32C3 gvs/firmware/gvs_controller
arduino-cli monitor -p /dev/cu.usbmodem1101 -c baudrate=115200
```

- With **no WiFi SSID** the board stays on Bluetooth only (`BLE: GVS-zapper advertising`), WiFi is off and the HTTP server does not start. This saves the battery. With an SSID it joins the network, or if it can't within 10 s it makes its own hotspot at `http://192.168.4.1/`.
- Never leave the example token (`change-me`) or the example hotspot password. `make_secrets.sh` writes random ones, and never overwrites an existing file.
- The firmware has `#if` guards for the esp32 core 2.x and 3.x LEDC and watchdog APIs. It was built against core 3.3.12 with the `huge_app` partition scheme for the BLE stack (`--fqbn esp32:esp32:XIAO_ESP32C3:PartitionScheme=huge_app` if the sketch doesn't fit).
- The boot log must show the PWMs attached. If it prints `FAULT: ledc attach failed`, the duty resolution is wrong for this chip's clock (the firmware uses 10 bits).

Check what the board says at idle:

```
{"mode":"idle","cmd_ma":0.000,"meas_ma":0.027,"relay":-1,"hv":0.00,"boost_pct":0.0,"cooldown_ms":0,"pulses_logged":0,"hour_full":false,"fault":false,"msg":""}
```

## 4. Relays

Both relay modules should be **off** at idle. If a relay's LED is lit with nothing commanded, find out whether that is the module's power LED or the coil really being energized (listen for a click, or beep COM ↔ NO). If a relay really is energized at idle, the module is active-low: set `RELAY_ACTIVE_LOW = true` and reflash.

## 5. Battery feed wire

Do this only after flashing. Solder the black wire from the XIAO's BAT+ (or the LiPo's red lead) to **S1 D19**. Keep the solder small: D19 sits next to relay 1's − pin (GND). You may put a switch in this wire as an "arm" switch.

- With the board off, D19 ↔ GND must not beep.
- Power up. `status` should show `hv` of about 3.5 to 3.9 V (the battery through the diode). I read 3.85 to 3.89 V.

## 6. Boost tuning (no electrodes)

Use a freshly charged battery.

```bash
python3 gvs/tools/bench.py boost-sweep --target 22
```

or by hand, from the serial monitor: `boost 5`, then step up 5% at a time. Stop when HV reaches **20 to 24 V** on a full battery. **Never go above 28 V.** Feel Q1, the inductor and the diode for heat. Write the result into `BOOST_PCT`, reflash, then send `boost 0`. The firmware refuses any pulse until `BOOST_PCT` is set. My result, 45%: HV about 21 V open, 17 V at 2 mA into 2.2 kΩ ([TESTING.md](TESTING.md)).

## 7. Dummy loads

Nobody attached. A 2.2 kΩ resistor across the two electrode leads, a meter across it (volts ÷ 2.2 = mA).

- Idle: 0 V across the load.
- 1 mA DC: about 2.2 V. 2 mA: about 4.4 V. `pol=1` flips the sign. A sine swings both ways.
- `ma=5` clamps to 2. `ms=10000` stops at 3 s. A second pulse inside 5 s is refused (cooldown).
- `stop`, the kill switch and the reset button each take the output to 0 V.
- With a 4.7 kΩ load the current is about 1.6 mA, which is the compliance limit (`status` still says 2).

`python3 gvs/tools/bench.py limits` checks the clamps, the maximum duration, the cooldown and stop, and prints PASS or FAIL for each. Do not go on if anything fails.

## 8. On a person

Only after steps 1 to 7 have passed, with a second person present, seated, kill switch in hand, on battery with the laptop off its charger. The full procedure, the ladder and the stop conditions are in [`research/gvs.md`](../research/gvs.md) section 9, and the skin prep and electrode checks in [HARDWARE.md](HARDWARE.md) and [`gvs/DEBUG.md`](../gvs/DEBUG.md). In short: fresh pads, gel-to-gel under about 1 kΩ, 0.5 mA first and 0.25 mA steps, never above 2.0 mA.

## 9. The software

- **UNO Q and fun mode:** [`uno_q/README.md`](../uno_q/README.md) and `uno_q/fun/start_fun.sh`.
- **The packet pipeline and its dashboard:** `uno_q/pipeline/start_pipeline.sh`, and [SOFTWARE.md](SOFTWARE.md).
- **TRIBE v2 at enrollment:** [`tribe/README.md`](../tribe/README.md).
- **The Mac's Bluetooth relay:** `gvs/tools/ble_bridge.py`, run in Terminal.app (the Claude app can't hold Bluetooth permission), for the browser tilt page at `http://127.0.0.1:8765/`.
