# UNO Q as a Tailscale exit node with tshark capture

Researched 2026-11-07 from the web only. Nothing was run on the board, no adb, nothing committed.
Labels used throughout: **[SRC]** sourced fact (URL given), **[INF]** my inference, **[UNK]** not found anywhere.

## Summary

- Hardware facts are well sourced: QRB2210 quad A53 2.0 GHz, Debian 13 trixie arm64, 2 GB or 4 GB RAM, 16 or 32 GB eMMC, Wi-Fi 5 + BT 5.1, **no Ethernet**, one USB-C. Kernel seen in the wild is 6.16.x.
- Tailscale itself is routine on Debian trixie (official apt repo, sysctl forwarding, `--advertise-exit-node`). Nobody has published "Tailscale on UNO Q". Whether the stock kernel has TUN is **[UNK]**; one command on the board settles it (`ls /dev/net/tun`).
- Capture only works in **kernel mode**. In userspace-networking mode there is no tunnel interface and `capture.sh` on `tailscale0` fails. Kernel 6.16 is above Tailscale's 6.2 threshold, so UDP GRO forwarding applies, but the board's only uplink is Wi-Fi, so expect modest throughput **[INF]**.
- Field names in `capture.sh` are all valid up to Wireshark 4.6.9 per the official field reference. QUIC SNI via `tls.handshake.extensions_server_name` is plausible (dissector hands Initial CRYPTO frames to TLS) but I found no doc that states it outright, and one report says tshark 3.6.2 failed where 4.0.5 worked. Test it on a real capture; the runbook has a check.
- The adb `offline` problem has **no sourced fix**. The evidence is thin: a cable/hub list, `kill-server`, stale adb forwarding (Windows), and a udev/login issue (Linux). Ranked attempts are in section 2. The way around it: if the board ever got Wi-Fi + SSH, skip adb entirely.
- ESP32: the single USB-C is the problem (it is also the adb/power port, and host mode needs a *powered* PD dongle or a debugfs force). Simplest design, already in `pipeline/README.md`: ESP32 stays on the Mac, board streams `capture.sh` over SSH.
- iPhone: exit node routes all default-route traffic **[SRC]**. Private Relay / Limit IP Address Tracking interplay is not documented anywhere I could reach; turn both off for the demo **[INF]**.

---

## 1. UNO Q hardware and access

| Fact | Value | Label / source |
|---|---|---|
| MPU | Qualcomm Dragonwing QRB2210, quad Cortex-A53 @ 2.0 GHz | SRC https://docs.arduino.cc/hardware/uno-q/ |
| MCU | STM32U585, Cortex-M33 up to 160 MHz, 2 MB flash, 786 kB SRAM | SRC same page |
| RAM variants | 2 GB or 4 GB | SRC https://docs.edgeimpulse.com/hardware/boards/arduino-uno-q.md ; Arduino page says "Recommended with the 4 GB RAM UNO Q variant" |
| Storage | 16 GB or 32 GB eMMC (16 GB "fills up faster than you would think") | SRC Edge Impulse page above; https://raspberry.tips/en/arduino/arduino-uno-q-debian-ssh . Arduino hardware page does not state it |
| OS | Debian 13 "trixie" arm64 | SRC raspberry.tips page above; image repo defaults to trixie: https://github.com/arduino/arduino-deb-images |
| Kernel | 6.16.7-g0dd6551ae96b seen on one board; `arduino/linux-qcom` branch `qcom-v7.0.0-unoq` also exists | SRC https://forum.arduino.cc/t/getting-a-usb-wifi-dongle-working-on-the-uno-q/1456444.md ; https://github.com/arduino/linux-qcom . Check your own with `uname -r` |
| Wi-Fi/BT | Wi-Fi 5 dual-band (2.4/5 GHz), BT 5.1, onboard antenna (WCBN3536A) | SRC Arduino hardware page |
| Ethernet | None onboard. Only via a USB-C dongle/hub | SRC Arduino hardware page; hub: https://store.arduino.cc/products/usb-c-hub |
| Network stack | NetworkManager (`nmcli`) | SRC raspberry.tips; arduino-deb-images lists NetworkManager + wpa_supplicant |
| User / password | user `arduino`; factory password `arduino` until App Lab first-time setup is done, then your own | SRC raspberry.tips; Edge Impulse; https://www.kevsrobots.com/blog/arduino-uno-q-wifi-setup.html . Arduino's own hardware page does not state it |
| Bridge | systemd service `arduino-router` links Linux and MCU. Stopping it cuts sketches off | SRC raspberry.tips |
| Docker | App Lab's Bricks run in Docker containers on the board; do not delete them | SRC raspberry.tips |
| Python version | **Not stated anywhere I found** | UNK. `arduino-deb-images` does not list python3 as an image package (build dependency only), so do not assume it is there. Check on the board |

### Getting a shell

1. **adb over USB-C** (the documented path). Arduino docs: connect over USB-C, `adb devices`, `adb shell`; up to a minute for the device to appear; may ask for password `arduino` if App Lab setup never ran. SRC https://github.com/arduino/docs-content/commit/7fc5e426f6fd7923364f453bb78dc309a788cecf (search-result summary of the Arduino docs source; the rendered user-manual page would not load for me).
2. **SSH over Wi-Fi.** `ssh arduino@<boardname>.local`, or by IP if `.local` fails (noted as common on macOS). SRC https://github.com/arduino/docs-content/pull/2685/files
3. **App Lab terminal.** Exists; I found no page specifying it. UNK.
4. **Serial console.** No source found for a Linux debug UART on the UNO Q. UNK. (Note: the MCU-side serial `/dev/cu.usbmodem...` is the sketch/bootloader, not a Linux login.)
5. **Keyboard + HDMI** via a powered PD USB-C hub, login `arduino`/`arduino`. SRC Edge Impulse page.

### Enabling SSH

- Completing App Lab's first setup (name, password, Wi-Fi) turns SSH on. If skipped: from an adb shell run `arduino-app-cli system network-mode enable`. SRC https://github.com/arduino/docs-content/pull/2685/files
- One forum reply says without that command SSH listens only on loopback. SRC https://forum.arduino.cc/t/app-can-recognize-uno-q-but-i-cant-connect-it-with-app-lab/1461569 (reply 8, unconfirmed).
- Older Edge Impulse instructions install openssh-server by hand (`sudo apt install openssh-server -y; sudo systemctl enable ssh; ...`). SRC https://docs.edgeimpulse.com/hardware/boards/arduino-uno-q.md . Use only if `network-mode enable` does not produce a listener.

### Headless Wi-Fi

From an adb shell: `sudo nmcli dev wifi connect "SSID" password "PASS"` (add `hidden yes` for hidden SSIDs), then `hostname -I`. SRC Edge Impulse + kevsrobots pages above. Captive-portal networks (hotel/campus) will not work from nmcli alone; kevsrobots notes App Lab stalls on them. For a hackathon venue, use a phone hotspot **[INF]**.

---

## 2. adb `offline`

**Honest state of the evidence:** no source documents your exact symptom (`offline`, "read failed", both adb 32 and 37). What exists:

- Cable must carry data, not charge only; wait ~30 s after power-on; `adb kill-server && adb start-server`; direct to the computer, not via a hub; "not compatible with Apple USB-C hubs and may not work through some third-party hubs." SRC https://www.kevsrobots.com/blog/arduino-uno-q-wifi-setup.html and https://docs.edgeimpulse.com/hardware/boards/arduino-uno-q.md
- Linux: `ADB device is offline` in App Lab's DevTools was fixed by **logging out and back in after udev rules** (killall adb and cable swaps did not help). Not relevant on macOS (no udev), but it shows the symptom can be a host-permission issue. SRC https://forum.arduino.cc/t/no-response-from-choose-a-board/1451438
- Windows: App Lab left a stale adb forward; `taskkill /F /IM adb.exe` plus closing App Lab fixed it. SRC https://forum.arduino.cc/t/app-can-recognize-uno-q-but-i-cant-connect-it-with-app-lab/1461569
- That same thread: reflashing the board image did not help the OP.
- App Lab's own adb handling (port, bundled binary, whether it fights a second server): **UNK**, no doc found.
- "unauthorized" is a different state (kevsrobots says check for a prompt); `offline` is not covered. The board has no screen, so there is no on-board RSA prompt; the "adb approval" the user gave was macOS letting Homebrew's adb run (exit 137 earlier), not a device authorisation **[INF]**.
- Network adb (`adb connect <ip>:5555`): no UNO Q source. UNK. Do not count on it.

**Ranked things to try [INF, general adb practice plus the sources above]:**

1. Quit Arduino App Lab fully. `pkill -f adb` (kills every server including App Lab's bundled one), confirm with `pgrep -fl adb`.
2. Unplug, wait 10 s, power-cycle the board (unplug USB-C), plug straight into a Mac port with a known data cable, no hub, no Apple dongle. Wait a full 60 s.
3. Check macOS sees the USB device at all: `system_profiler SPUSBDataType | grep -i -B2 -A8 -E "arduino|qualcomm|05c6|2341"`. If it is missing, it is cable/port; if present but adb `offline`, it is adbd/handshake.
4. Start ONE adb: `adb kill-server; adb start-server; sleep 3; adb devices -l`. Use only one of the two binaries; Homebrew's 37.0.2 is the better first choice (current) **[INF]**.
5. A different Mac USB port / bus (some ports sit behind an internal hub).
6. If the board is stuck from a previous state, a hard reboot is the only reliable reset I know of. The reset button on the board restarts the MCU, which may not restart Linux **[INF]**.
7. Remember the heartbeat/boot LED animation kevsrobots says to wait for is on the LED matrix. Your `matrix_status` sketch replaces it, so the matrix is no longer a "Linux is up" signal **[INF]**. Wait 60 s by the clock instead.
8. Fallback with no adb: if the board has ever been given Wi-Fi, try `ssh arduino@<boardname>.local` and look for it on the router. Also try `arduino-cli board list` (Arduino says it shows the IP for network boards, https://github.com/arduino/docs-content/pull/2685/files).
9. Last resort: reflash the image (Arduino's flashing tool). Per the forum thread it did not cure that user's problem, so it is expensive and uncertain. It would also wipe anything on the board.

---

## 3. Tailscale on the board

### Install (Debian trixie, arm64)
Official apt repo commands for trixie, SRC https://pkgs.tailscale.com/stable/ . The page does not name arm64 on the trixie section; Tailscale publishes arm64 packages generally **[INF]**. Alternative one-liner, SRC https://tailscale.com/kb/1031/install-linux : `curl -fsSL https://tailscale.com/install.sh | sh`.

### Kernel TUN
- Tailscale on Linux uses `/dev/net/tun`; kernel mode is the default. SRC https://tailscale.com/kb/1177/kernel-vs-userspace-routers
- Does the UNO Q kernel have TUN: **UNK.** I found no config for it. Arduino's other board kernels in `arduino/meta-arduino` have `CONFIG_TUN=y` (Portenta X8/X9), which says nothing about the Qualcomm kernel. The module list exists under `/lib/modules/6.16.7-.../kernel/` and `/proc/config.gz` is implied to exist (forum thread above). The board runs Docker for App Lab, which needs bridge/veth/netfilter, but not TUN **[INF]**.
- Check on the board: `ls -l /dev/net/tun; zcat /proc/config.gz | grep -E 'CONFIG_TUN|CONFIG_NETFILTER_XT_TARGET_MASQUERADE|CONFIG_NF_NAT'; sudo modprobe tun`. Tailscale's own docs say to `modprobe tun` and add `tun` to `/etc/modules-load.d/`. SRC https://tailscale.com/docs/install/linux.md (search-result summary).
- If TUN is absent, a kernel rebuild (`arduino/linux-qcom`, or the `arduino-deb-images` kernel package) is the real fix; userspace networking is a fallback that breaks the capture plan (below).

### IP forwarding (persistent)
Tailscale's documented commands, SRC https://tailscale.com/kb/1019/subnets :
```
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
```
Note: IPv6 forwarding with NetworkManager-managed Wi-Fi can disable RA acceptance on wlan0 (kernel behaviour, `accept_ra` drops to 0 when forwarding=1 unless set to 2) **[INF]**. If the board loses its IPv6 default route after this, set `net.ipv6.conf.wlan0.accept_ra = 2`. Not needed if the venue network is IPv4 only.

### Advertise, approve
SRC https://tailscale.com/kb/1103/exit-nodes :
```
sudo tailscale set --advertise-exit-node
sudo tailscale up
```
(`sudo tailscale up --advertise-exit-node` also works; `uno_q/README.md` has it plus `--ssh`.) Then **you** open the printed login URL and, in the admin console, Machines, device menu, Edit route settings, Use as exit node. If you use custom ACLs you need a grant to `autogroup:internet`; defaults allow everyone. Client: pick the exit node in the app.

### UDP GRO forwarding
Tailscale recommends on exit nodes/subnet routers (needs Tailscale >= 1.54 and Linux >= 6.2 for the offloads, SRC https://tailscale.com/kb/1320/performance-best-practices):
```
NETDEVS=$(( ip -4 -o route get 8.8.8.8; ip -6 -o route get 2001:4860:4860::8888 ) 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "dev") print $(i + 1)}' | sort -u)
for NETDEV in $NETDEVS; do sudo ethtool -K "$NETDEV" rx-udp-gro-forwarding on rx-gro-list off; done
```
Kernel 6.16 satisfies the version rule. Whether the Wi-Fi driver (`wlan0`) supports `rx-udp-gro-forwarding` is **UNK**; `ethtool -K` will print "Could not change any device features" if not **[INF]**. Persistence: Tailscale's page covers `networkd-dispatcher` and NetworkManager profiles; the board uses NetworkManager, so use their NetworkManager variant (page above). For a one-sitting demo, running the command after each boot is enough.

### Does tshark see exit-node traffic?
- **Kernel mode (default as root):** the OS forwards packets and Tailscale does not rewrite them; TCP is end-to-end from the origin. SRC https://tailscale.com/kb/1177/kernel-vs-userspace-routers . So decrypted client traffic crosses `tailscale0` **[INF from that statement]**: capture there sees phone IPs (100.x) as `ip.src`, with real destinations. This matches `capture.sh`.
- **Userspace mode:** gVisor netstack terminates TCP/UDP from the peer and opens new outbound sockets; non-TCP/UDP is dropped; recommended only for low bandwidth. SRC same page. Userspace mode uses no TUN device, so **no `tailscale0`** (the userspace page https://tailscale.com/kb/1112/userspace-networking says it runs where a tunnel device cannot be created, SOCKS5/HTTP proxy model). Capturing on `wlan0` instead shows only the board's own outbound connections (src = board IP, all phones merged) **[INF]**, and `capture.sh`'s per-source separation is lost.
- Conclusion: if `/dev/net/tun` is missing, stop and fix the kernel (or capture on wlan0 and accept the loss of per-device attribution).

### Throughput
No benchmark for QRB2210 found. **[INF]** Four A53 at 2 GHz handle WireGuard (kernel module in Linux >= 5.6, built into Tailscale's path) fine in the tens of Mbit/s. The hard limit is that the only uplink is Wi-Fi: the encrypted tunnel arrives on `wlan0` and the egress leaves on `wlan0`, so one half-duplex radio carries both. Realistic cap is roughly half of the Wi-Fi link rate. tshark dissection on top will be the first CPU bottleneck, not WireGuard. For a phone doing Instagram this is enough; speed tests will look poor. Measure with `iperf3` or a speed test on the phone, plus `top`.

---

## 4. tshark on Debian arm64

- Package: `tshark` (apt, trixie; version unverified, run `tshark --version`). The official field reference lists these through 4.6.9: `tls.handshake.extensions_server_name` (Server Name, string, 3.0.0-4.6.9, https://www.wireshark.org/docs/dfref/t/tls.html), `dns.qry.name` (1.0.0-4.6.9), `dns.a` (IPv4, 1.12.0-4.6.9), `dns.aaaa` (IPv6, 1.12.0-4.6.9) (https://www.wireshark.org/docs/dfref/d/dns.html), `http.host` (1.0.0-4.6.9, https://www.wireshark.org/docs/dfref/h/http.html). SRC. Before 3.0 the TLS prefix was `ssl.`; you are on trixie so `tls.` is right. The ip/ipv6/tcp/udp/frame fields in `capture.sh` are standard and I did not check each page **[INF]**.
- `-T fields -e ...` with `-Y` is single pass; `-2` is not needed for live capture. SRC https://www.wireshark.org/docs/man-pages/tshark.html
- Non-root capture: the Debian package asks "Should non-superusers be able to capture packets?"; answering yes installs dumpcap with capabilities and group `wireshark` **[INF, from Debian packaging; the Wireshark wiki points to README.Debian instead]**. Generic manual recipe, SRC https://wiki.wireshark.org/CaptureSetup/CapturePrivileges :
  ```
  sudo groupadd --system wireshark       # skip if exists
  sudo gpasswd -a $USER wireshark
  sudo chgrp wireshark /usr/sbin/dumpcap   # path may be /usr/bin/dumpcap
  sudo chmod o-rx /usr/sbin/dumpcap
  sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/dumpcap
  ```
  then log out/in or `newgrp wireshark`. Simplest for the demo: run capture under `sudo` and skip groups.
- Preseed the question non-interactively: `echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections` **[INF, verify with `getcap $(which dumpcap)`]**.
- **QUIC SNI.** Mechanism: the QUIC dissector decrypts Initial packets (keys derive from the public connection ID, RFC 9001) and passes CRYPTO data to the TLS handshake dissector; source comment says the ClientHello is contained in the Initial packet. SRC https://gitea.osmocom.org/osmith/wireshark/src/commit/d01b85c028f912b3100d2590067bd2a8ef705c34/epan/dissectors/packet-quic.c (search snippet), https://docs.rs/flowscope/0.26.0/flowscope/quic/struct.QuicInitial.html (same mechanism from a Rust library, not Wireshark). Out-of-order CRYPTO frames are reassembled (commit "Handle out-of-order CRYPTO frames", https://gitea.osmocom.org/osmith/wireshark/commit/cb3fd3b5cde74fe0b164b19898950184935dacba). So a populated `tls.handshake.extensions_server_name` on QUIC packets is expected **[INF]**, but **no page I could reach states it**. One Stack Overflow summary says tshark 3.6.2 (Ubuntu 22.04) could not read many Initial fields while 4.0.5 could (https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/76086848/extract-sni-from-quic-initial-packet-pyshark; I could not re-open it to confirm, secondhand). Trixie ships a 4.x tshark **[INF]**. Caveats **[INF]**: only the Initial is readable; QUIC versions Wireshark does not know (or fresh draft/v2) may not decrypt; Encrypted Client Hello hides SNI entirely; `capture.sh` has no QUIC-specific column, so an SNI appears in column 10 only on the Initial packets.
- Cost on a small board: dissection of every packet is the load. QUIC decryption adds AES per Initial only. No measurements found. Expect one core busy at a few thousand packets/s **[INF]**.
- Load reduction **[INF]**: you cannot capture-filter to only handshakes, because the pipeline needs `frame.len` of every packet for flow volume/shape (`pipeline/README.md`). So:
  1. Keep `-n` (already), `-l` (already). Add `-B 16` to avoid kernel drops.
  2. Leave snaplen at default. A truncated snaplen below ~1600 bytes would cut ClientHellos (Chrome-class ClientHellos and QUIC Initials are ~1200+ bytes).
  3. Add `-f "not port 22"` is moot on `tailscale0`; skip.
  4. If the board saturates, switch to a two-stage design: `dumpcap -i tailscale0 -b filesize:50000 -b files:10 -w /tmp/cap.pcapng` (cheap, no dissection; ring-buffer syntax SRC man page above) and run tshark offline on the Mac over `scp`'d files. Loses real-time stimulus.
  5. Watch with `top` and `tshark -i tailscale0 -a duration:30 -q -z io,stat,0` for packet rate.

---

## 5. iPhone side

- Exit node routes `0.0.0.0/0` and `::/0`, capturing all traffic not already going to a subnet router or app connector; Tailscale-to-Tailscale traffic stays on the overlay; local network is excluded only if "Allow Local Network Access" is on. SRC https://tailscale.com/kb/1103/exit-nodes
- Select from the top of the Tailscale app on iOS; admin must allow it. SRC same page.
- **Background behaviour, VPN on demand, battery on iOS: not covered** by that page. UNK. **[INF]** iOS keeps a VPN extension running while the VPN is active, but may suspend the app; expect some battery drain from the always-on tunnel. No numbers found.
- **iCloud Private Relay:** Apple says DNS records are encrypted and neither party sees the destination address; Apple's page does not mention SNI, VPNs or Limit IP Address Tracking. SRC https://support.apple.com/en-us/102602 . Community threads say Private Relay can be disabled when a VPN is active on Mac, and one reports iPhone/iPad ran both side by side (https://discussions.apple.com/thread/255027503, search summary, not verified). UNK whether Tailscale's exit node triggers it. What I believe but could not source **[INF]**: Private Relay covers Safari, DNS lookups and unencrypted app HTTP, not other apps' TLS; so Instagram app traffic is unaffected, but Safari traffic would hide its destination from the exit node. Turn Private Relay off for the experiment (Settings, Apple ID, iCloud, Private Relay).
- **Limit IP Address Tracking** (Wi-Fi setting): no source found for its effect on exit nodes. Turn it off for the test **[INF]**.
- SNI is not hidden by any of these; only ECH hides it **[INF]**. DNS may be DoH/DoT/encrypted on iOS in some configs (iOS encrypted DNS profiles), which would leave `dns.*` empty and rely on SNI **[INF]**; the pipeline already learns names from SNI too.

---

## 6. Pipeline on the board, and the ESP32 link

- Python: version UNK. Trixie's python3 is 3.13 if installed **[INF]**; `pipeline` is stdlib-only except `pyserial` for ESP32. Check `python3 --version; python3 -m venv /tmp/v` on the board. If `ensurepip` is missing: `sudo apt-get install -y python3-venv python3-pip`. `python3-serial` is the Debian package name for pyserial **[INF]**.
- The board needs no pipeline at all if the Mac runs it. `pipeline/README.md` already uses `ssh unoq ./capture.sh | python -m gvs_pipeline live --esp32 /dev/cu.usbmodem1101`. **Recommendation: do that.** It also keeps the 786 kB-class load off the board **[INF]**.
- ESP32 on the board's USB-C: **hard**.
  - One USB-C, also the power and adb port. Arduino docs: a USB-C dongle with external power delivery; "the UNO Q does not supply power to the USB-C dongle". SRC https://docs.arduino.cc/hardware/uno-q/ and the quote relayed in https://forum.arduino.cc/t/uno-q-usb-port-not-working-if-board-powered-from-5v/1442207.md
  - The port defaults to device mode if booted without a USB-C cable negotiating CC (host role never set). Workaround from that thread (linux-qcom issue #2): `echo host > /sys/kernel/debug/usb/4e00000.usb/mode`, with a boot service at https://github.com/Psalmustrack/arduino-uno-q-usb-fix (thread says tested with Zigbee dongle, cameras, keyboards via a hub; I did not open the repo). Arduino staff reportedly called the unpowered case unsupported.
  - Arduino's 8-in-1 hub is the supported route (USB-A 2.0 port included). SRC https://store.arduino.cc/products/usb-c-hub
  - Mixed field reports on dongles: https://forum.arduino.cc/t/arduino-uno-q-app-lab-as-a-usb-host-to-an-uno-r3-python-environment-sees-0-devices/1433482 (title only; I did not open it).
  - You cannot have the Mac on the USB-C for adb and the ESP32 on it at the same time. After Wi-Fi + SSH works, adb is no longer needed.
- ESP32 over Wi-Fi: the pipeline README says the firmware's HTTP endpoint is unauthenticated and untested; usable on a closed hotspot, not elsewhere. The board would need a client to POST to it (not written).

---

## Bring-up runbook

Legend: **[YOU]** a step only you can do. Everything else is a paste. Run on the Mac unless it says BOARD.

### A. Reach the board (Mac)
```
pkill -f adb; pgrep -fl adb || echo "no adb running"      # expect: "no adb running"  (also quit Arduino App Lab)
```
**[YOU]** Unplug USB-C, wait 10 s, plug straight into a Mac port (data cable, no hub/Apple dongle). Wait 60 s.
```
system_profiler SPUSBDataType | grep -i -E -B2 -A6 "arduino|qualcomm"   # expect: a device entry; none = cable/port
adb kill-server; adb start-server; sleep 3; adb devices -l   # expect: <serial>  device ... (not "offline")
adb shell                                                    # expect: arduino@<name>:~$ prompt; password "arduino" if asked
```
If still `offline`, work down section 2. Do not continue until you have a shell (adb or SSH).

### B. Wi-Fi and SSH (BOARD, via adb shell)
```
nmcli device status                                           # expect: wlan0  wifi  disconnected (or connected)
sudo nmcli dev wifi connect "SSID" password "PASS"            # expect: Device 'wlan0' successfully activated
hostname -I                                                   # expect: your LAN IP
arduino-app-cli system network-mode enable                    # expect: no error; SSH starts listening
```
From the Mac (use a hotspot, not a captive-portal network):
```
ssh arduino@<ip-or-name>.local        # expect: password prompt, then a shell
```
Set a real password: `passwd`.

### C. Facts the plan depends on (BOARD) — send me this output
```
uname -a; cat /etc/os-release | head -3; free -m; df -h /; python3 --version
ls -l /dev/net/tun; zcat /proc/config.gz | grep -E 'CONFIG_TUN=|CONFIG_NF_NAT=|MASQUERADE'; ip -br addr
```
Stop here if `/dev/net/tun` is missing and `CONFIG_TUN` is not `y`/`m` (see section 3).

### D. tshark (BOARD)
```
echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tshark   # expect: installs, no prompt
sudo gpasswd -a $USER wireshark                                  # then log out and in
getcap $(which dumpcap)                                          # expect: cap_net_admin,cap_net_raw=eip
tshark --version | head -1                                       # note: 4.x wanted for QUIC SNI
```

### E. Tailscale (BOARD)
```
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt-get update && sudo apt-get install -y tailscale ethtool
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf                   # expect: both = 1
sudo tailscale up --advertise-exit-node --ssh                    # expect: prints a login URL
```
**[YOU]** Open the login URL in a browser and sign in.
**[YOU]** Admin console, Machines, the board's menu, Edit route settings, tick "Use as exit node". Save.
```
tailscale status                                                 # expect: board listed, "offers exit node"
ip -br link show tailscale0                                      # expect: tailscale0 UNKNOWN/UP  (must exist = kernel mode)
sudo ethtool -K wlan0 rx-udp-gro-forwarding on rx-gro-list off   # expect: no output; "Could not change any device features" = driver lacks it, ignore
```

### F. Phone and capture
**[YOU]** On the iPhone: Settings, iCloud, Private Relay off; Wi-Fi network "Limit IP Address Tracking" off; Tailscale app, Exit Node, pick the board.
Check the phone's public IP matches the board's network (any "what is my IP" site).
```
# BOARD: smoke test, 20 s, does the interface see phone traffic?
sudo tshark -i tailscale0 -n -a duration:20 -q -z io,stat,0      # expect: nonzero frames
# BOARD: run the real script
sh /home/arduino/capture.sh | head -20                           # expect: tab lines, col 2 = 100.x.x.x
# QUIC SNI check: open Instagram/YouTube on the phone, then
sudo tshark -i tailscale0 -n -a duration:30 -Y "quic && tls.handshake.type == 1" -T fields -e ip.src -e tls.handshake.extensions_server_name
                                                                 # expect: hostnames; empty = QUIC SNI not exposed on this tshark
```
Then, from the Mac: `ssh unoq ./capture.sh | python -m gvs_pipeline live` (dry run) before adding `--esp32`.

Watch load while it runs: `top -b -n1 | head -15`; if tshark pegs a core or drops packets, use the dumpcap ring-buffer fallback in section 4.

---

## Open questions

1. Why adb is `offline`. No source covers it. Does the upload to the MCU go through adb on this core (then adb worked at upload time and something changed after)? I could not determine that; look at the upload log.
2. Does the UNO Q kernel have `CONFIG_TUN` (and NAT/MASQUERADE for forwarding)? The runbook step C answers it. If not, a kernel rebuild is needed; I did not find how Arduino packages the kernel (`linux-image-qcom-next` is the image default, https://github.com/arduino/arduino-deb-images).
3. Does Wireshark on trixie expose QUIC Initial SNI in `tls.handshake.extensions_server_name`? Plausible, not documented in what I could read; runbook F tests it.
4. Python version on the board.
5. Does the Wi-Fi driver support `rx-udp-gro-forwarding`?
6. Does Tailscale's exit node on iPhone coexist with Private Relay, and what does Private Relay do to what the exit node sees? Apple's page was silent.
7. iOS background persistence and battery of an always-on exit node: no data.
8. Real exit-node throughput and tshark CPU cost on QRB2210: no benchmark found; measure.
9. Whether `network-mode enable` is still the right command on your App Lab / image version (docs are 2026 and moving).
10. ESP32 transport: Mac-side serial (recommended) vs board USB host (needs powered PD hub and the host-mode force) vs Wi-Fi (needs a client that does not exist yet).

Provenance notes: several sources above came through a search tool's summary rather than a page I read in full. I marked those. Searches never returned a Tailscale-on-UNO-Q write-up. One fetched GitHub page (arduino/linux-qcom) contained text addressed to AI coding assistants; it is irrelevant to this research and I ignored it.
