# TRIBE v2 for the GVS project

Researched and run 2026-11-07. Repo commit `af58661` (2026-06-23), HF weights sha `f894e78`.

## Summary

1. TRIBE v2 takes a video (or audio, or text) file and predicts the average subject's fMRI response: one 20,484-value map per second on the fsaverage5 cortical surface. The released checkpoint covers cortex only, so the striatum, accumbens and other reward circuitry are not in the output.
2. It ran end to end on the GPU box, but on CPU. vLLM (gemma-4-26B, `--gpu-memory-utilization 0.90`) holds 21.3 of 23 GB VRAM, and I left it alone. A 12 s clip took 27 min, about 25 of them in V-JEPA2.
3. Licences: TRIBE code and weights are CC-BY-NC-4.0. Llama-3.2-3B is gated, but the HF account already logged in on the box (AryaGarg23) has access, so nothing is blocked.
4. Nothing in the output measures reward or "engagement". The defensible proxy is predicted visual, auditory and dorsal-attention cortex drive, scored against two fixed anchor clips. That says how much sensory and attentional load the content puts on you, not how much you want it.
5. Recommendation: use TRIBE offline at enrollment to suggest each bucket's weight, capped by the user's own weight, and pre-render a brain-map movie for the demo. Don't promise a live brain map: even on a free 3090 Ti the video backbone is estimated to run slower than real time (inference, see below).

## Facts

### Inputs and preprocessing

- Input is a single `.mp4/.avi/.mkv/.mov/.webm`, `.wav/.mp3/.flac/.ogg` or `.txt` file. Exactly one per call. `tribev2/demo_utils.py:42-46, 286-290` — https://github.com/facebookresearch/tribev2/blob/main/tribev2/demo_utils.py
- For video, the audio track is pulled out to `<video>.wav` next to the video file. Audio and video are chunked into 30–60 s pieces, then words are transcribed. `demo_utils.py:75-91`, and neuralset `events/transforms/audio.py` (`ExtractAudioFromVideo` writes `Path(filepath).with_suffix(".wav")`).
- The text modality needs word-level timings. The repo gets them by shelling out to `uvx whisperx <wav> --model large-v3 --language en --compute_type float16 --align_model WAV2VEC2_ASR_LARGE_LV60K_960H`. Language is hard-coded to English, and `float16` is hard-coded. `tribev2/eventstransforms.py:86-137` — https://github.com/facebookresearch/tribev2/blob/main/tribev2/eventstransforms.py
- If `<wav>.tsv` already exists, whisperx is skipped and the TSV is used (columns `text, start, duration, sequence_id, sentence`). `eventstransforms.py:173-185`. I used this to get past the CPU float16 failure (see below).
- Only spoken words reach the text model. On-screen text, such as a DM thread, is not read by the text pathway, because words come only from `Audio` events (`eventstransforms.py:165`). The only way on-screen text gets in is through the video model's pixels.
- Text input goes through gTTS (Google TTS, needs network) and then whisperx. `demo_utils.py:98-130`.
- Sentence splitting uses spaCy and auto-downloaded `en_core_web_lg` (400 MB) on first run (seen in `run2.log`).

### Backbones (from the released `config.yaml`, https://huggingface.co/facebook/tribev2/blob/main/config.yaml)

- Text: `meta-llama/Llama-3.2-3B`, layers at 0.5/0.75/1.0 depth (config lines 193-200). The paper (§5.2) says each word is embedded with the preceding 1,024 words as context. https://arxiv.org/html/2605.04326v1
- Audio: `facebook/w2v-bert-2.0` (config 320-365). The paper says it runs on 60 s chunks and is resampled from 50 Hz to 2 Hz.
- Video: `facebook/vjepa2-vitg-fpc64-256` (config 366-449, `clip_duration: 4.0`). Every 0.5 s it feeds 64 frames covering the preceding 4 s (paper §5.2; neuralset `extractors/video.py` `_get_data`, `max_frames = 64` for vjepa2).
- `facebook/dinov2-large` appears in the config as `image_feature`, but `features_to_use` is `[text, audio, video]` (config 485-490), so it isn't used. The demo notebook's markdown mentions DINOv2 anyway: https://github.com/facebookresearch/tribev2/blob/main/tribe_demo.ipynb
- Head: an 8-layer, 8-head transformer, hidden 1152, `low_rank_head: 2048`, 25 training subjects averaged at inference (`average_subjects=True`, `demo_utils.py:218`). Checkpoint `best.ckpt` is 708,856,138 bytes (HF `x-linked-size`).
- Modality dropout p=0.3 during training, so a missing modality (silent video, no speech) is in-distribution (paper §5.3).

### Output

- `preds` has shape `(n_TRs, 20484)`: fsaverage5, left hemisphere then right, 10,242 vertices each. README: https://github.com/facebookresearch/tribev2#quick-start. Our run gave `(12, 20484)` for 12 s.
- Temporal resolution: features at 2 Hz, output at 1 Hz (`neuro.frequency: 1.0`, top-level `frequency: 2.0`, config 142 and 485; paper: "decimate... from 2 Hz to 1 Hz").
- Predictions are already shifted 5 s back to undo hemodynamic lag (`neuro.offset: 5.0`, config 143; README). So pred[t] lines up with stimulus second t.
- Only non-empty seconds are returned (`remove_empty_segments=True`, `demo_utils.py:148, 370-372`). Our log: `Predicted 12 / 100 segments (12.0% kept)`.
- Units: training targets were z-scored per vertex per session and detrended (config 158-164; paper §5.8), so predictions are in roughly z-units around a naturalistic-movie baseline.
- Clip length: there's no minimum in the code. Windows are 100 TRs (`duration_trs: 100`, config 497), and inputs are chunked to 30–60 s. A 12 s clip worked.
- **Cortex only in the release.** The paper also trained subcortical models on 8,802 Harvard-Oxford voxels in 8 regions: hippocampus, lateral ventricles, amygdala, thalamus, caudate, putamen, pallidum, accumbens (paper §5.8, https://arxiv.org/html/2605.04326v1). The repo has the training grid `tribev2/grids/run_subcortical.py`. But the HF repo ships only `best.ckpt` + `config.yaml`, with an fsaverage5 projection (https://huggingface.co/api/models/facebook/tribev2, config 144-154). There is no released subcortical checkpoint, so no accumbens or striatum predictions.

### Licences and gating

- TRIBE v2 code: CC-BY-NC-4.0 (`LICENSE`, README badge). Weights: CC-BY-NC-4.0 (HF model card front matter, https://huggingface.co/facebook/tribev2). A non-commercial hackathon demo is fine; a product built on it is not.
- `meta-llama/Llama-3.2-3B` is gated (`"gated": "manual"`, Llama 3.2 Community License) — https://huggingface.co/meta-llama/Llama-3.2-3B. **The HF login already on the box (`~/.cache/huggingface/token`, user AryaGarg23) has access.** `huggingface_hub.auth_check` returned ACCESS OK, and the run downloaded and used it. I did not enter or accept anything.
- `facebook/vjepa2-vitg-fpc64-256`: apache-2.0, not gated. `facebook/w2v-bert-2.0`: MIT, not gated (HF API `cardData.license`).
- whisperX: BSD-2-Clause (https://github.com/m-bain/whisperX). Diarization isn't used, so pyannote (gated) is not needed.
- **Trap:** `tribev2.utils.get_hcp_labels` calls `mne.datasets.fetch_hcp_mmp_parcellation(..., accept=True)` (`tribev2/utils.py:220-221`), which silently accepts the HCP-MMP1 terms. `summarize_by_roi`, `get_topk_rois` and `PlotBrain.annotate_rois` all go through it. I did not call any of them. I used nilearn's Destrieux surface atlas instead (fsaverage5, no click-through).

### Requirements

- Python `>=3.11` (`pyproject.toml`). The HF card badge says 3.10+, but pyproject wins. `torch>=2.5.1,<2.7` and `numpy==2.2.6` pin it in practice. uv resolved torch 2.6.0+cu124. The box's system Python 3.14 is too new for torch 2.6 wheels (inference from torch's published wheel set; I used uv's CPython 3.12.14, which worked).
- Paper compute: feature extraction for training took 24 h on 128 V100-32GB; training took 24 h on one V100 (paper §5.2-5.4). There are no published inference VRAM or speed figures.
- Disk after one run on the box: HF hub cache 16 GB (Llama 3.2 3B, V-JEPA2-g, w2v-bert, tribev2, faster-whisper-large-v3 2.9 GB), torch hub 1.2 GB (wav2vec2 align model), venv 7.4 GB, uv cache 11 GB (includes the whisperx tool env; some of it may predate this run). Budget about 35 GB.

## What ran on the GPU box

Everything is under `/root/tribev2` in WSL. Copies of the scripts are in `tribe/` (`tribe/README.md` is the workflow).

### Install (worked)

```bash
git clone https://github.com/facebookresearch/tribev2 ~/tribev2
cd ~/tribev2
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install -e ".[plotting]"
python -c "import torch,sys;print('python',sys.version.split()[0],'torch',torch.__version__,'cuda',torch.version.cuda,torch.cuda.is_available())"
# python 3.12.14 torch 2.6.0+cu124 cuda 12.4 True
```

The install took 17 s; uv already had most wheels cached.

### GPU state (blocker for a GPU run)

```
nvidia-smi: 21272MiB / 23028MiB used, process /python3.12
ps: /usr/bin/python3 /usr/local/bin/vllm serve --model dhruvil237/gemma-4-26B-A4B-it-W4A16 --gpu-memory-utilization 0.90 ...
```

That leaves about 1.7 GB free. Llama-3.2-3B alone is about 12.8 GB in fp32 (inference: `neuralset/extractors/text.py:335-350` passes no dtype unless `device="accelerate"`). I ran everything on CPU with `CUDA_VISIBLE_DEVICES=""` so the vLLM service wasn't disturbed.

### Test clip

`make_video.sh`: gTTS speech ("Hello. This is a short test clip for the brain encoding model...") muxed onto ffmpeg `testsrc2`, 640x360, 30 fps, 12 s → `work/test12.mp4`.

### Attempt 1: official path on CPU (failed in whisperx)

`run_cpu.py` = README quick start + `config_update` moving the three extractors to CPU:

```python
cpu = {"data.text_feature.device": "cpu", "data.audio_feature.device": "cpu",
       "data.video_feature.image.device": "cpu", "data.num_workers": 0}
model = TribeModel.from_pretrained("facebook/tribev2", cache_folder="/root/tribev2/cache", device="cpu", config_update=cpu)
df = model.get_events_dataframe(video_path=video); preds, segments = model.predict(events=df)
```

```
CUDA_VISIBLE_DEVICES="" .venv/bin/python run_cpu.py work/test12.mp4
...
ValueError: Requested float16 compute type, but the target device or backend do not support efficient float16 computation.
```

The cause is `eventstransforms.py:108`, where `compute_type = "float16"` is hard-coded. This only bites without a GPU.

### Attempt 2: CPU transcription stand-in, then official predict (worked)

`transcribe_cpu.py` runs the same uvx whisperx command with `--compute_type int8` and writes `work/test12.tsv` (`wav.with_suffix(".tsv")`, the path the repo checks) using the repo's own JSON→TSV conversion. `ExtractWordsFromAudio` then picks the TSV up.

```bash
cd ~/tribev2 && export CUDA_VISIBLE_DEVICES=""
.venv/bin/python transcribe_cpu.py work/test12.wav     # 27 words in 25.6s (incl. model load)
.venv/bin/python run_cpu.py work/test12.mp4
```

Output excerpts (`work/run2.log`):

```
[   11.6s] peakRSS=1.6GB events built: {'Word': 27, 'Sentence': 3, 'Audio': 1, 'Video': 1, 'Text': 1}
[16:54:03 INFO] Preparing extractor: text          # Llama download ~50 s + 27 words embedded, 65 s total
[16:55:08 INFO] Preparing extractor: audio         # 38 s incl. download
[16:55:46 INFO] Preparing extractor: video
Encoding video: 100%|██████████| 24/24 [24:18<00:00, 60.79s/it]
[17:20:41 INFO] Preparing extractor: subject_id
INFO - Predicted 12 / 100 segments (12.0% kept)
[ 1615.4s] peakRSS=12.9GB predicted: preds.shape=(12, 20484)
pred stats: mean 0.0322 std 0.1659 min -0.6705 max 0.8073
Elapsed (wall clock) time: 26:57.00   Maximum resident set size: 12859172 KB   Exit status: 0
```

CPU throughput: V-JEPA2-g took **about 61 s per 0.5 s step**, about 2 CPU-hours per minute of video. Text and audio are negligible next to that.

### ROI summary (`roi_score.py`, nilearn Destrieux on fsaverage5)

```
preds (12, 20484) vertices per group {'visual': 2368, 'auditory': 618, 'language': 1619, 'dorsal_attention': 1262, 'vmpfc_ofc': 842}
visual            mean +0.1025  per-TR 0.04 0.03 0.05 0.09 0.09 0.08 0.10 0.14 0.17 0.17 0.15 0.14
auditory          mean +0.1608  per-TR 0.25 0.24 0.25 0.32 0.31 0.31 0.24 0.24 0.02 -0.06 -0.13 -0.08
language          mean +0.0014
dorsal_attention  mean +0.1777
vmpfc_ofc         mean -0.0179
```

As a sanity check, auditory cortex is high while the TTS voice talks (0–8 s) and drops below zero once the speech ends. The rendered mean map (`research/tribe_v2/test12_mean.png`) lights the superior temporal gyrus and occipital pole. That's what you'd expect, and it's the only behavioural check I ran.

No background processes were left running. `pgrep -af run_cpu` is empty, and the GPU is back at 21271 MiB, which is vLLM alone.

## Blockers

1. **GPU is occupied.** vLLM (`vllm serve --model dhruvil237/gemma-4-26B-A4B-it-W4A16 --gpu-memory-utilization 0.90`, PID 4512) holds 21.3/23 GB. To run TRIBE on the GPU, the user has to stop that service or restart it with a lower `--gpu-memory-utilization`. I didn't touch it. Until then, measured CPU speed is about 2 h of compute per minute of video.
2. **whisperx float16 on CPU.** This only matters while the GPU is unavailable. Workaround: `transcribe_cpu.py` writes the `.tsv` first. On GPU the stock path should work (not verified here).
3. **No released subcortical model.** Reward-circuit predictions (accumbens, caudate, putamen) would need training the `run_subcortical` grid on the four fMRI datasets. That isn't hackathon-sized.
4. Not a blocker, but needs a decision: the repo's HCP ROI helpers auto-accept the HCP-MMP1 terms (`utils.py:220`). If the user wants Glasser parcels, they should read those terms and decide. Destrieux works without them.

## Recommendation

**What TRIBE can honestly do here:** it can estimate how hard a piece of content drives visual, auditory and attention cortex in an average viewer. Reels (fast cuts, faces, music, speech) should score well above DMs (a mostly static UI; typed text doesn't reach the text pathway). That's a defensible, physiologically framed reason for a bucket's weight. "Reward" or "addictiveness" is not defensible: the reward circuitry isn't in the released output, and vmPFC/OFC is the region group TRIBE predicts least well (inference: the paper's encoding-score maps are highest in sensory cortex; our vmPFC/OFC values sit near zero).

**Use 1, offline weight at enrollment (do this).** While the packet exemplar is being captured, the user screen-records the same 2 minutes on the iPhone. Run TRIBE on that recording and compute:

```
R      = visual ∪ dorsal_attention ∪ auditory vertices      (Destrieux groups in roi_score.py; 4,248 vertices)
s(c)   = mean over TRs t and vertices v∈R of preds_c[t, v]
s0     = s(neutral anchor)  : 60 s of a static iPhone home-screen screenshot, silent (ffmpeg -loop 1)
s1     = s(high anchor)     : the Sintel trailer the official notebook uses (https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4)
w_tribe(b) = clip((s(b) - s0) / (s1 - s0), 0, 1)
weight(b)  = min(w_tribe(b), user_cap(b))        # user_cap = the existing --weight; 0 for DMs stays 0
```

Both anchors are fixed files scored once, so a bucket's weight doesn't depend on which other buckets are enrolled. This is my pick over per-clip min-max normalisation, which is what the public Spaces do and which makes every clip score 0–100 no matter what. Name the number "predicted sensory–attentional drive" in the UI and the pitch.

Wiring: `python -m gvs_pipeline enroll ig_reels reels_2min.tsv --weight 0.9 --tribe-score reels_2min.preds.npy` would set `weight = min(0.9, w_tribe)`. TRIBE only ever lowers a weight below the user's cap, so it can't raise stimulation past what the user chose. The ESP32 caps still apply regardless. Not implemented, since you asked for research only.

Runtime per 2-minute enrollment clip:
- CPU, measured rate: 240 steps × 61 s ≈ **4 h**. Too slow. If the GPU stays occupied, score a 30 s excerpt (≈1 h).
- Free 3090 Ti, *inference, not measured*: V-JEPA2-g is about 1B params over 8,192 tokens per step, roughly 30 TFLOP. At fp32 that's an estimated 1–2 s per step, so **4–8 min per 2-minute clip**, plus about 1 min for whisperx, Llama and w2v-bert. It needs about 13–15 GB free VRAM (inference from the 12.9 GB peak CPU RSS).

**Use 2, live brain map (don't build it live).** At 2 V-JEPA steps per second of video, a free 3090 Ti in fp32 is estimated at 2–4× slower than real time (inference). The pipeline is also file-based, with whisperx run per file and a 4 s look-back per step. A rolling 10 s chunk would show up roughly 30–50 s late (inference). For the demo, pre-render instead: run TRIBE on the enrollment recordings and make a brain movie with `PlotBrain(mesh="fsaverage5").plot_timesteps_mp4(preds, "reels_brain.mp4", segments=segments)` (`tribev2/plotting/base.py:431`). Play it side by side with the screen recording; it's already time-aligned because of the 5 s offset. Then say on stage that it was computed ahead of time.

**Better idea:** use TRIBE as the explainer, not the controller. Show the judges the reels-vs-DMs contrast map, made from two enrollment recordings with mean(preds_reels) − mean(preds_dms) plotted on fsaverage5. That's the same kind of in-silico contrast the paper validates (§2.5-2.6, §5.9). It visually justifies why reels get stimulated and DMs don't, while packets do the live work they're actually able to do.

## Open questions

- GPU timings and VRAM are estimates. They need one run with vLLM stopped: the same `run_cpu.py` without `CUDA_VISIBLE_DEVICES=""` and without the `config_update` (so the stock `device: cuda`).
- Would bf16 autocast on V-JEPA2 (about 4× faster on tensor cores, inference) shift the features enough to change predictions? Untested.
- iPhone recordings are 9:16 portrait. How the V-JEPA2 processor crops or resizes them to 256 px wasn't checked; it might center-crop away most of a reel.
- Do reels and DMs actually separate on `s`? Only real recordings will show it. The 12 s synthetic clip shows the pipeline works, not that the score discriminates.
- The neutral anchor (a static home screen) is my pick. A black silent clip is the other obvious choice; I didn't compare them.
- iOS screen recording includes app audio by default (inference, from iOS behaviour, not checked on this phone). If the audio is missing, auditory and text inputs drop out, which modality dropout tolerates but which lowers `s`.
