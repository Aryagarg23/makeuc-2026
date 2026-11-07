# pipeline

Packet lines → per-service sliding flow windows → one-shot bucket → confirm over consecutive steps → stimulus intensity → ESP32.

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
- Domain enrolled by exactly one bucket → that bucket, intensity = bucket weight.
- Domain shared by several buckets (Instagram reels and DMs both use `cdninstagram.com`) → decided by flow shape against each bucket's shape *for that domain*. The winner must beat the runner-up at ≥ 0.90 and be close in absolute terms, otherwise nothing. Weight never breaks the tie (`test_shared_domain_not_decided_by_weight`).
- Named but not enrolled → nothing. Never shape-matched (`test_named_unenrolled_service_never_stimulated`).
- No name ever seen → nearest flow-shape prototype if similarity ≥ 0.80. Intensity scales from 0 at threshold up to the weight (`test_unnamed_flow_falls_back_to_shape`).
- Windows are 3 s long and slide every 1 s (`--window`, `--step`). A service moving under 5 kB/s in a window is never stimulated (`classify.py:min_bytes`).
- A stimulus fires only when the same bucket is the strongest decision for 2 consecutive steps (`--confirm`), then nothing fires for 5 s, which is the firmware cooldown (`trigger.py`, `test_refractory_matches_firmware_cooldown`). On synthetic reels the first stimulus lands within 4 s of onset (`test_reels_fire_within_four_seconds_at_3s_windows`). Why 3 s and 2 steps: `../research/conditioning.md` §2 and `../research/traffic_fingerprinting.md` §5. Duration is 500–2000 ms, capped at the firmware ceiling.
- Buckets remember the window length they were enrolled at. Classifying at a different `--window` is refused, because three of the six features scale with window length.
- The ESP32 enforces its own caps regardless: arming, 5 s cooldown, 30 per hour, max duty (`esp32/README.md`).

## TRIBE weight cap

`enroll ... --tribe CLIP.tribe.json --tribe-anchors NEUTRAL.tribe.json HIGH.tribe.json` sets the weight to `min(--weight, drive)`. Here `drive` is TRIBE's predicted cortical drive for the bucket's screen recording, placed between two anchor clips (`gvs_pipeline/tribe.py`, `../tribe/README.md`). It can lower the weight you chose, never raise it.

## Reels vs DMs (same app)

Enroll both, with weight 0 on the one you don't want punished:

```bash
python -m gvs_pipeline enroll ig_reels reels_2min.tsv --weight 0.9
python -m gvs_pipeline enroll ig_dms dms_2min.tsv --weight 0
python -m gvs_pipeline enroll ig_other feed_2min.tsv --weight 0   # feed, stories, explore: shares the CDN too
```

Enroll and run at the same `--window`/`--step`.

Record each exemplar doing only that thing (2 min of reels, 2 min of chatting with a photo or two). On synthetic traffic (`tests/test_reels_vs_dms.py` at 10 s, `tests/test_sliding.py` at 3 s): a reels window gets `ig_reels` at intensity 0.90, a photo opened in a DM goes to `ig_dms` (weight 0, no stimulus), and texting stays under 50 kB, so it never triggers.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pyserial pytest hypothesis
.venv/bin/python -m pytest -q
```

## Not done

- TRIBE v2 is used only at enrollment, on screen recordings. It isn't in the live loop: the exit node sees encrypted packets, and TRIBE runs slower than real time.
- Not run against real tailnet traffic yet. Every test uses synthetic flows, including the Instagram ones. Real Instagram may share one QUIC connection between API and media, prefetch reels while you're in DMs, or open DM videos that look like reels. Only real exemplar captures will show whether the shapes separate.
- Not run on the UNO Q yet.
- The ESP32 link uses serial only. The firmware's HTTP endpoint is unauthenticated and untested.
