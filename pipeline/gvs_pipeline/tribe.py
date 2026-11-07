"""Bucket weight from TRIBE v2 clip scores (tribe/score_clip.py writes the *.tribe.json files).

drive = (s_bucket - s_neutral) / (s_high - s_neutral), clipped to [0, 1], where the anchors are
two fixed clips scored once (tribe/make_anchors.sh). The enrolled weight is min(user weight, drive):
TRIBE can lower what the user chose, never raise it. The score is predicted cortical drive, not a
reward or craving measure (research/tribe_v2.md).
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def load_score(path: Path) -> float:
    s = float(json.loads(Path(path).read_text())["score"])
    if not math.isfinite(s):
        raise ValueError(f"{path}: score is not finite")
    return s


def drive(score: float, neutral: float, high: float) -> float:
    if not high > neutral:
        raise ValueError(f"high anchor ({high}) must score above neutral ({neutral})")
    return min(max((score - neutral) / (high - neutral), 0.0), 1.0)


def capped_weight(user_weight: float, score: float, neutral: float, high: float) -> float:
    return min(min(max(user_weight, 0.0), 1.0), drive(score, neutral, high))
