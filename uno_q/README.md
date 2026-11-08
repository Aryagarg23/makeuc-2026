# UNO Q (matrix status, capture box)

State as of 2026-11-07: the MCU half is built and uploaded. The Linux half could
not be reached (adb stays offline), so Linux, Tailscale and tshark setup has not
been done. Details under "Not verified".

## Measured
- Board: /dev/cu.usbmodem3279494652, arduino-cli 1.5.1, FQBN arduino:zephyr:unoq, core arduino:zephyr 1.1.0 (installed).
- Libraries already present (user dir): Arduino_RouterBridge 0.4.4, Arduino_RPClite 0.3.1, MsgPack 0.4.2. Arduino_LED_Matrix comes with the core.
- Sketch `matrix_status/matrix_status.ino` compiled: 90640 bytes flash (11%), 36312 bytes RAM (13%).
- Upload via `arduino-cli upload` finished; OpenOCD reported the STM32U57/U58 flashed and "shutdown command invoked". The matrix itself was not seen (headless), so display correctness is unverified.
- adb: Arduino's bundled adb 32.0.0 and Homebrew adb 37.0.2 both list the board as `offline` (transport `327949465`). It never became `device` over ~10 minutes, after `reconnect`, server restarts and `ADB_LIBUSB=1`. `adb shell` => `adb: device offline`.
- Homebrew's adb was killed with exit 137 until the user approved adb; after that it ran.

## MCU API (Bridge, msgpack-rpc)
- `show(bucket_index:int, intensity:float)`: digit 0-9 at cols 2-4, rows 1-5; bar at cols 9-11, filled from the bottom, round(intensity*8) rows. Out-of-range values are clamped (bucket outside 0-9 draws no digit).
- `clear()`.
- Registered with `provide_safe` so handlers run in loop context, as the manual recommends for hardware calls.

## Rebuild / upload
    arduino-cli core install arduino:zephyr
    arduino-cli lib install Arduino_RouterBridge
    arduino-cli compile -b arduino:zephyr:unoq matrix_status
    arduino-cli upload -p /dev/cu.usbmodem3279494652 -b arduino:zephyr:unoq matrix_status

## Packet pipeline + rules dashboard on the board (`pipeline/`)

    uno_q/pipeline/start_pipeline.sh demo            # synthetic traffic made on the board, dry run
    uno_q/pipeline/start_pipeline.sh mac en0 0.5     # the Mac's tshark on en0 -> board; stimulates at up to 0.5 mA
    uno_q/pipeline/start_pipeline.sh stop

- **Where it runs:** the pipeline (`pipeline/gvs_pipeline`, pure stdlib) runs on the board under `/home/arduino/gvs/pipeline`.
- **Dashboard:** on the arya-gvs hotspot at `http://10.42.0.1:8081/#key=KEY`, and on the Mac at `http://127.0.0.1:18081/#key=KEY` (adb forward). The start script prints both links.
- **Key:** every `/api` call needs the key in `store/dashboard.key`, because friends share the hotspot. Without it they get 401 and see no traffic.
- **Stimuli:** with an MA argument, stimuli go through fun mode's Bluetooth link (`fun_server.py` `/cmd` on :8080), so fun mode must be running.
- **Packets come from the Mac,** for three reasons:
  - The board has no tshark and no internet to install it.
  - Raw capture needs root (sudo asks for a password).
  - The Mac's tshark needs capture permission (Wireshark's ChmodBPF, or sudo); you have to set that up.
- **Measured 2026-11-08 (demo mode):**
  - Without the key, `/api/state` returns 401; with it, 200.
  - A rule POSTed with the key is saved to `store/rules.json` on the board.
  - That rule fires every 10 s (the refractory gap), at 50% for 1250 ms.
  - The board's clock is ~14 months behind (no internet), so stimulus ages are measured on the board's clock.
- **Not verified yet:** `mac` mode (needs capture permission on the Mac) and a real stimulus through fun mode from the pipeline.

## Linux side (once adb works)
Default password for a never-configured board is `arduino` (per element14 review; the Arduino docs page fetched did not state it).

    adb shell                                        # enter Linux
    adb push linux/bridge_show.py /home/arduino/
    adb shell "sudo apt-get install -y python3-msgpack"
    adb shell "python3 /home/arduino/bridge_show.py show 3 0.5"
    adb shell "python3 /home/arduino/bridge_show.py clear"

Exit code 0 means the router answered `error=None`. Then, still to do on the board:
tshark (`DEBIAN_FRONTEND=noninteractive apt-get install -y tshark`, answer yes to non-root capture, add the user to `wireshark`),
Tailscale from Tailscale's Debian apt repo, `/etc/sysctl.d/99-tailscale.conf` with `net.ipv4.ip_forward = 1` and `net.ipv6.conf.all.forwarding = 1`,
then `sudo tailscale up --advertise-exit-node --ssh` and open the login URL it prints (you do this; it was not attempted).
Also check on the board for the classifier: `python3 --version`, `python3 -m venv /tmp/v`, `free -m`, `df -h /`.

## linux/capture.sh
tshark on tailscale0, tab-separated, no header. Columns: 1 frame.time_epoch, 2 ip.src, 3 ip.dst, 4 ipv6.src, 5 ipv6.dst, 6 tcp.dstport, 7 udp.dstport, 8 frame.len, 9 dns.qry.name, 10 tls.handshake.extensions_server_name, 11 http.host. The script has no QUIC-specific column: QUIC SNI shows in column 10 only if tshark decrypts the Initial packet.

## Not verified
- Anything on the Linux side: Debian version, CPU/RAM, WiFi/IP, python3 version, venv, free RAM/disk. All unmeasured because adb is offline.
- `bridge_show.py` and `capture.sh` were only syntax-checked locally, never run on the board.
- The matrix drawing, the Bridge round trip, and that the sketch boots and registers after upload.
- Tailscale install, IP forwarding, tshark group capture, the login URL.
- Whether `float` args round-trip as the sketch expects (the script always sends floats).
