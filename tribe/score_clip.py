"""Score one clip with TRIBE v2: predicted sensory-attentional drive.

Run in WSL on the GPU box inside ~/tribev2/.venv (setup_tribe.sh):

  python score_clip.py CLIP.mp4                 # inference + score
  python score_clip.py CLIP.mp4 --from-preds    # re-score an existing CLIP.preds.npy

Writes CLIP.preds.npy (T x 20484, fsaverage5) and CLIP.tribe.json:
  {"clip", "seconds", "device", "score", "groups": {group: mean}}
score = mean over time and over the union of the visual, auditory and dorsal-attention
vertices (roi_score.GROUPS). It is predicted cortical drive, not reward: the released
checkpoint is cortex only (research/tribe_v2.md).

Device: cuda when at least NEED_VRAM is free, else cpu. On cpu the stock whisperx call fails
(float16 hard-coded, tribev2/eventstransforms.py:108), so the transcript is written first with
int8 and the repo picks up <wav>.tsv instead.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from roi_score import group_masks

DRIVE_GROUPS = ("visual", "auditory", "dorsal_attention")
NEED_VRAM = 16e9  # Llama-3.2-3B alone is ~12.8 GB; V-JEPA2 ViT-g and w2v-bert on top
CPU = {
    "data.text_feature.device": "cpu",
    "data.audio_feature.device": "cpu",
    "data.video_feature.image.device": "cpu",
    "data.num_workers": 0,
}


def pick_device() -> str:
    import torch

    if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] >= NEED_VRAM:
        return "cuda"
    return "cpu"


def predict(clip: Path, device: str) -> np.ndarray:
    from tribev2 import TribeModel

    kw = {"device": device}
    if device == "cpu":
        kw["config_update"] = CPU
    model = TribeModel.from_pretrained("facebook/tribev2", cache_folder=str(Path.home() / "tribev2" / "cache"), **kw)
    try:
        df = model.get_events_dataframe(video_path=clip)
    except ValueError as e:
        if device != "cpu" or "float16" not in str(e):
            raise
        from transcribe_cpu import transcribe

        transcribe(clip.with_suffix(".wav"))  # the failed call already extracted the wav
        df = model.get_events_dataframe(video_path=clip)
    preds, _ = model.predict(events=df)
    return np.asarray(preds)


def drive(preds: np.ndarray) -> tuple[float, dict[str, float]]:
    masks = group_masks()
    union = np.zeros(preds.shape[1], dtype=bool)
    for g in DRIVE_GROUPS:
        union |= masks[g]
    groups = {g: float(preds[:, m].mean()) for g, m in masks.items()}
    return float(preds[:, union].mean()), groups


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--from-preds", action="store_true")
    ap.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    a = ap.parse_args()
    npy = a.clip.with_suffix(".preds.npy")
    t0 = time.time()
    if a.from_preds:
        preds, device = np.load(npy), "cached"
    else:
        device = pick_device() if a.device == "auto" else a.device
        print(f"device {device}", file=sys.stderr, flush=True)
        preds = predict(a.clip, device)
        np.save(npy, preds)
    score, groups = drive(preds)
    rec = {"clip": a.clip.name, "seconds": int(preds.shape[0]), "device": device,
           "score": score, "groups": groups, "wall_s": round(time.time() - t0, 1)}
    a.clip.with_suffix(".tribe.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
