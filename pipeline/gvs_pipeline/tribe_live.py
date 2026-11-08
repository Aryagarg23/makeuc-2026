"""Live TRIBE scores -> bucket intensities.

tribe/screen_chunks.py appends {"t0", "t1", "score", ...} lines (epoch seconds) for each scored
screen chunk. The network decides *when* to stimulate within seconds; TRIBE, 30-60 s behind,
decides *how hard*: a chunk's drive goes to the bucket the classifier saw over the same seconds,
smoothed, and that bucket's weight becomes min(user weight, smoothed drive). TRIBE can lower what
the user chose, never raise it (tribe.capped_weight's rule, live).

Attribution is by time, not by device: if the phone and the laptop both carry enrolled traffic in
the same seconds, a laptop chunk can be credited to the phone's bucket. Named, not solved.
"""
from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path

from .classify import Bucket
from .tribe import drive

ALPHA = 0.5  # smoothing: each new chunk moves the drive halfway
MIN_WINDOWS = 2  # a chunk needs at least this many decided windows to be attributed
KEEP_S = 600.0


class Feed:
    """Reads only the lines appended to scores.jsonl since the last call."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.pos = self.path.stat().st_size if self.path.exists() else 0

    def new(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open() as fh:
            fh.seek(self.pos)
            chunk = fh.read()
        complete, _, partial = chunk.rpartition("\n")
        self.pos += len(complete) + (1 if complete or chunk.startswith("\n") else 0)
        out = []
        for line in complete.splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return out


class Attributor:
    """Remembers which bucket won each window, to credit a TRIBE chunk to what was on the network."""

    def __init__(self, window_s: float) -> None:
        self.window_s = window_s
        self.wins: deque[tuple[float, str | None]] = deque()

    def note(self, window_start: float, bucket: str | None) -> None:
        self.wins.append((window_start, bucket))
        while self.wins and self.wins[0][0] < window_start - KEEP_S:
            self.wins.popleft()

    def bucket_for(self, t0: float, t1: float) -> str | None:
        hits = [b for s, b in self.wins if s < t1 and s + self.window_s > t0]
        named = Counter(b for b in hits if b is not None)
        if not named:
            return None
        b, n = named.most_common(1)[0]
        return b if n >= MIN_WINDOWS and n * 2 > len(hits) else None


def apply(bucket: Bucket, d: float, alpha: float = ALPHA) -> None:
    user = bucket.user_weight if bucket.user_weight is not None else bucket.weight
    bucket.user_weight = user
    bucket.tribe_drive = d if bucket.tribe_drive is None else (1 - alpha) * bucket.tribe_drive + alpha * d
    bucket.weight = min(user, bucket.tribe_drive)


def step(feed: Feed, att: Attributor, buckets: list[Bucket], neutral: float, high: float) -> list[dict]:
    """Apply every new chunk; return one record per chunk for the live log."""
    by_name = {b.name: b for b in buckets}
    out = []
    for rec in feed.new():
        d = drive(float(rec["score"]), neutral, high)
        name = att.bucket_for(float(rec["t0"]), float(rec["t1"]))
        r = {"tribe_chunk": [rec["t0"], rec["t1"]], "drive": round(d, 3), "bucket": name}
        if name in by_name:
            apply(by_name[name], d)
            r.update(weight=round(by_name[name].weight, 3), tribe_drive=round(by_name[name].tribe_drive, 3))
        out.append(r)
    return out
