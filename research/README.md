# Research, 2026-11-07

Five sourced write-ups, done while the GVS hardware is being soldered. Each one tags its claims as sourced or inferred, and each ends with its own open questions.

| File | Question | What it changed |
|---|---|---|
| `gvs.md` | Currents, waveform, safety, circuit, bench and on-head tests | Firmware change spec, not yet applied (see below) |
| `conditioning.md` | Does pairing content with GVS condition anything, and with what timing? | Pipeline: 3 s windows sliding every 1 s, 2-step confirm (`pipeline/gvs_pipeline/trigger.py`) |
| `traffic_fingerprinting.md` | Can reels be told from DMs in encrypted metadata? | Same window change; `ig_other` weight-0 bucket; capture plan |
| `uno_q_exit_node.md` | Turning the UNO Q into a Tailscale exit node with capture | Bring-up runbook |
| `tribe_v2.md` | What TRIBE v2 is, and running it on the GPU box | `tribe/` scorer and `--tribe` weight cap at enrollment |

## What the research says, short

- **GVS gives a tilt or sway jolt plus tingling within 1–2 s, not nausea.** Nausea needs ±2 mA slow sinusoids for 9–21 minutes, then takes 15–30 min to clear (`gvs.md` §Summary). The project's stimulus is a seconds-scale vestibular punisher.
- **Mostly operant punishment, so delay matters.** 10 s tumbling windows put the stimulus 5–20 s late. The pipeline now fires about 4 s after onset on synthetic reels (`pipeline/tests/test_sliding.py::test_reels_fire_within_four_seconds_at_3s_windows`). Nausea pairs with taste, not visual cues (Garcia & Koelling), which is another reason not to aim for nausea (`conditioning.md` §3).
- **Biggest risk to reels-vs-DMs:**
  - The two share `cdninstagram.com`, often the same multiplexed QUIC connection, and the app's own DNS cache.
  - No published work separates this pair.
  - Only real captures will tell (`traffic_fingerprinting.md` §8, Capture plan).
  - DNS answers likely won't be visible on the exit node, so SNI is the naming source.
- **UNO Q risks:**
  - adb `offline` has no documented cure.
  - TUN support in the stock kernel is unconfirmed. Without it there's no `tailscale0` to capture on.
  - One Wi-Fi radio carries both the tunnel and the exit traffic (`uno_q_exit_node.md`).
- **TRIBE v2:**
  - Runs on the GPU box today, CPU only.
  - Cortex-only output, so no reward signal.
  - Slower than real time, so it's an offline enrollment cap plus a pre-rendered brain movie, not a live loop (`tribe_v2.md`).

## Blocked / still open

- **Firmware change** (`gvs.md` §7: bipolar sine burst, two PWM channels, enable line, mA units, 10 s cooldown). Blocked until the front end is known: does 0 V command mean 0 mA, or does mid-scale? With a mid-scale-zero front end, today's firmware idles at full negative current (`gvs.md` Summary 4). Needs the front-end schematic, or at least: supply rails, the V→I stage, the sense resistor, and the hardware current limit.
- **TRIBE on GPU** needs the vLLM server on the box stopped or capped. Its timings are estimates.
- **Real exemplar captures** (reels, DMs, DMs with media, feed) haven't been recorded. All classifier results are on synthetic traffic.
- **UNO Q** is untouched since adb went `offline`.
