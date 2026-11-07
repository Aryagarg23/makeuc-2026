# pipeline

Packet lines → per-service flow windows → one-shot bucket → stimulus intensity → ESP32.

Pure Python 3 (stdlib; `pyserial` only for the ESP32 link), so it runs on the Mac or on the UNO Q's Linux side.

## Input

tshark `-T fields -E separator=/t` lines in the column order of `gvs_pipeline/packets.py:COLUMNS`. `uno_q/linux/capture.sh` must emit the same order.

## Commands

```bash
python -m gvs_pipeline enroll short_video tiktok_session.tsv --weight 0.8
python -m gvs_pipeline classify some_capture.tsv
ssh unoq ./capture.sh | python -m gvs_pipeline live --esp32 /dev/cu.usbmodem1101
```

`live` without `--esp32` is a dry run: one JSON line per window, nothing sent.

## How a window is decided (`gvs_pipeline/classify.py`)

- Names come from DNS answers, TLS SNI and HTTP Host, learned per IP (`flows.py:HostMap`). Services are registrable domains (`flows.py:service_of`; a short multi-label suffix list, not the full Public Suffix List).
- Enrolled domain → that bucket, intensity = bucket weight.
- Named but not enrolled → nothing. Never shape-matched (`test_named_unenrolled_service_never_stimulated`).
- No name ever seen → nearest flow-shape prototype if similarity ≥ 0.80. Intensity scales from 0 at threshold up to the weight (`test_unnamed_flow_falls_back_to_shape`).
- A window under 50 kB for a service is never stimulated.
- At most one stimulus per 10 s window. Duration is 500–2000 ms, capped at the firmware ceiling.
- The ESP32 enforces its own caps regardless: arming, 5 s cooldown, 30 per hour, max duty (`esp32/README.md`).

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pyserial pytest hypothesis
.venv/bin/python -m pytest -q
```

## Not done

- TRIBE v2 is not wired in. It takes video, audio and text. The exit node sees encrypted packets, so it gets hostnames and flow shape, not content.
- Not run against real tailnet traffic yet. Every test uses synthetic flows.
- Not run on the UNO Q yet.
- The ESP32 link uses serial only. The firmware's HTTP endpoint is unauthenticated and untested.
