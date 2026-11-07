# tribe

TRIBE v2 sets an upper bound on each bucket's weight from a screen recording of the enrollment session. It runs offline on the GPU box, not in the live loop. Findings and measurements are in `../research/tribe_v2.md`.

## What the number means

`score_clip.py` predicts the average viewer's cortical response (fsaverage5, one map per second) to a clip. It reports the mean over visual, auditory and dorsal-attention cortex. `gvs_pipeline/tribe.py` places that score between two fixed anchor clips:

- **neutral** (scores 0): a still frame with silence
- **high** (scores 1): the Sintel trailer

The enrolled weight is `min(your --weight, drive)`. TRIBE can lower your number, never raise it (`pipeline/tests/test_tribe.py::test_tribe_never_raises_user_weight`). This is predicted sensory and attentional load. It doesn't measure reward or craving, because the released checkpoint covers cortex only.

## Workflow

1. **Record on the iPhone** with the screen recorder and the mic on. Do this during each enrollment capture (2 min reels only, 2 min DMs only), so the packets and the video cover the same session.

2. **Set up the GPU box once** (WSL, as root):
   ```bash
   bash setup_tribe.sh
   mkdir -p ~/tribev2/gvs
   ```
   Then copy `score_clip.py`, `roi_score.py`, `transcribe_cpu.py` and `make_anchors.sh` into `~/tribev2/gvs`.

3. **Make the anchors once.** The neutral anchor works best with a home-screen screenshot from your phone:
   ```bash
   bash make_anchors.sh [home_screen.png]
   ```

4. **Score the anchors and each recording:**
   ```bash
   ../.venv/bin/python score_clip.py ~/tribev2/anchors/neutral.mp4
   ../.venv/bin/python score_clip.py ~/tribev2/anchors/sintel.mp4
   ../.venv/bin/python score_clip.py reels_2min.mp4
   ```

5. **Copy the `*.tribe.json` files back to the Mac and enroll:**
   ```bash
   python -m gvs_pipeline enroll ig_reels reels_2min.tsv --weight 0.9 \
     --tribe reels_2min.tribe.json --tribe-anchors neutral.tribe.json sintel.tribe.json
   ```

6. **For the demo,** `render.py CLIP.preds.npy out.png` draws the time-mean map. For a movie to play next to the screen recording, use TRIBE's own `plot_timesteps_mp4`.

## Cost

The GPU is held by the vLLM server (gemma-4-26B, `--gpu-memory-utilization 0.90`, about 21 of 23 GB). `score_clip.py` uses CUDA only when 16 GB is free, and otherwise falls back to CPU.

- **CPU (measured):** 27 min for a 12 s clip, with a 12.9 GB peak. A 2-minute recording would take about 4 h.
- **GPU (estimated, not run):** 4–8 min per 2-minute clip. It needs vLLM stopped or restarted with a lower memory setting.

## Verified / not verified

**Verified:**
- `score_clip.py --from-preds` on the box against the 12 s test clip's predictions. Output: score 0.133; auditory 0.161 and visual 0.103.
- `test_tribe.py` (7 tests).
- The full CPU inference path, which the research run exercised.

**Not run:**
- `score_clip.py` inference end to end, both its CUDA branch and its retry after the CPU float16 failure.
- `make_anchors.sh`.
- Scoring a silent clip: whisperx with zero words is untested.
- How V-JEPA2 crops a 9:16 iPhone recording.
- Whether reels and DMs score differently.
