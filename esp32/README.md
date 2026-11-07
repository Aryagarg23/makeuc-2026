# ESP32 GVS command controller

Receives stimulus commands from the Mac and drives one PWM pin that feeds the
command input of the user's separate analog GVS front end. This firmware is the
software safety layer; it is not a substitute for hardware current limiting.

## Measured chip facts (esptool, this board)
- ESP32-C3 (QFN32) revision v0.4, single core 160 MHz, Wi-Fi + BLE 5
- Embedded flash 4 MB (XMC, manufacturer 0x20 device 0x4016), no PSRAM (C3 has none)
- Crystal 40 MHz, USB-Serial/JTAG, MAC 64:e8:33:84:6b:0c, port /dev/cu.usbmodem1101

## Pin map (GPIO numbers)
| Function | GPIO | Notes |
|---|---|---|
| PWM out | 4 | LEDC, 20 kHz, 10-bit (0..1023). Fit an external ~10k pull-down to GND: the pin floats while the chip is in reset/bootloader, before firmware can drive it low. |
| E-stop in | 5 | INPUT_PULLUP. Switch to GND = E-stop. A broken wire reads HIGH (not tripped): this is not wire-break fail-safe. |
| SD SCK | 6 | SPI |
| SD MISO | 7 | SPI |
| SD MOSI | 10 | SPI |
| SD CS | 3 | |
GPIO 2, 8, 9 (strapping), 18/19 (USB), 11-17 (flash) are unused. GPIO 4-7 are
JTAG pins by default but free here because the USB-Serial/JTAG controller is used.
SD module wiring: VCC 3V3 (or 5V if the module has a regulator), GND, SCK->6, MISO->7, MOSI->10, CS->3.

## Protocol
Serial 115200, one JSON object per line, one JSON line per reply. Unknown or
unparsable input: `{"ok":false,"reason":"parse"}` (unknown cmd: `unknown_cmd`, bad stim fields: `bad_args`).
- `{"cmd":"status"}` -> `{"ok":true,"chip","device_name","uptime_ms","armed","sd","max_duty","stims_last_hour","last_stim_ms_ago"(null if none),"estop","active","wifi_ip"}`
- `{"cmd":"arm"}` -> armed; auto-expires after 600000 ms; refused (`estop`) while E-stop is low
- `{"cmd":"disarm"}`
- `{"cmd":"stim","bucket":"x","intensity":0..1,"ms":int}` -> `{"ok":true,"duty":<peak counts of 1023>,"ms":<clamped>,"intensity":<clamped>}` or `{"ok":false,"reason":...}`. Reasons: `estop`, `not_armed`, `busy`, `cooldown`, `hourly_limit`, `bad_args`.
- `{"cmd":"stop"}` -> output 0 immediately (stays armed; cooldown applies after an aborted stim)

HTTP (only if config has a non-empty wifi_ssid): `POST /cmd` with the same JSON body, same JSON reply, no authentication.

## Safety caps (compiled in `gvs_controller/safety.h`)
- intensity clamped to [0,1]; ms clamped to [50,2000]
- 200 ms linear ramp up and down inside the duration (shortened to ms/2 when ms < 400 so the peak is not exceeded)
- refuse when not armed; refuse within 5000 ms after the previous stim ended; refuse at 30 accepted stims in the rolling hour
- max_duty ceiling 0.6, default 0.4; `/config.json` may only lower it
- E-stop low: output 0, running stim aborted, armed=false, every pass of loop() (about 1 ms)
- output driven 0 first thing in setup(); see the pull-down note for the pre-firmware window

## SD card
Mount at boot; if it fails, `sd=false` and everything else works. `/config.json` keys: `max_duty` (float), `wifi_ssid`, `wifi_password`, `device_name`; missing keys keep defaults. Every stim attempt appends to `/log/trials.csv` (header `uptime_ms,bucket,intensity,duty,ms,result,reason`).

## Build and upload
```
cd esp32
python3 -m venv .venv && .venv/bin/pip install esptool pyserial
arduino-cli core install esp32:esp32
arduino-cli lib install ArduinoJson
arduino-cli compile --fqbn esp32:esp32:esp32c3:CDCOnBoot=cdc gvs_controller
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn esp32:esp32:esp32c3:CDCOnBoot=cdc gvs_controller
.venv/bin/python tools/serial_check.py /dev/cu.usbmodem1101
```
`CDCOnBoot=cdc` is required so `Serial` is the USB port.

## Verified on hardware (tools/serial_check.py)
status fields, disarmed at boot, stim before arm refused, arm, stim(2.0, 99999) accepted with ms=2000 and duty 409 (0.4*1023), a second stim refused (busy during the first, cooldown after stop), stop, malformed line -> parse, ms clamped up to 50, disarm.

## Not verified
- SD mount, config load, trial logging: no card wired (status showed sd=false, the no-card path).
- WiFi and HTTP /cmd: no SSID configured.
- E-stop: no switch wired; the pin read HIGH (estop=false) only. The LOW path is untested.
- PWM waveform was not measured with a scope or meter; duty values are the numbers sent to LEDC.
- Ramp shape, the 600 s arm expiry and the 30/hour limit were not exercised on the device.
- Output level during reset/bootloader is not controlled by firmware (use the pull-down).
- server.handleClient() can stall the loop for a slow HTTP client, delaying E-stop beyond 5 ms in that case.
