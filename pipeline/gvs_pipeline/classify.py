"""One-shot bucket classifier and stimulus intensity.

Enrollment: one labelled capture per bucket. Services carrying >=10% of the exemplar's
bytes or packets become the bucket's domain set. Each of those domains keeps its own
byte-weighted mean flow shape, and the bucket keeps an overall shape prototype.

Classification of one Observation:
- named service in exactly one bucket's domain set -> that bucket, confidence 1.
- named service shared by several buckets (Instagram reels and Instagram DMs both use
  instagram.com / cdninstagram.com) -> decided by flow shape against each candidate's
  shape *for that domain*; kept only if the winner clearly beats the runner-up.
- named service in no bucket -> None. We know what it is and it was not enrolled.
- unnamed service (no DNS/SNI seen, e.g. ECH or a flow that started before capture)
  -> nearest overall shape prototype, kept only above SHAPE_THRESHOLD.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .flows import N_FEATURES, UNKNOWN, Observation

DOMAIN_SHARE = 0.10  # share of exemplar bytes OR packets needed to join the domain set
SHAPE_SIGMA = 0.15
SHAPE_THRESHOLD = 0.80
SHARED_MARGIN = 0.90  # P(winner) among two candidates needed to decide a shared domain
SHARED_MAX_D2 = (3 * SHAPE_SIGMA) ** 2  # winner must also be this close in absolute terms
MIN_BYTES_PER_S = 5_000  # below this rate a window's traffic is background noise, never stimulated


def min_bytes(window_s: float) -> float:
    """The floor scales with window length so a 3 s window is held to the same rate as a 10 s one."""
    return MIN_BYTES_PER_S * window_s


@dataclass
class Bucket:
    name: str
    weight: float  # 0..1, how strongly the user wants to be conditioned against this bucket
    domains: set[str] = field(default_factory=set)
    shape: tuple[float, ...] = (0.0,) * N_FEATURES
    domain_shapes: dict[str, tuple[float, ...]] = field(default_factory=dict)
    window_s: float = 10.0  # window length the exemplar was summarised at
    tribe_drive: float | None = None  # TRIBE drive in [0, 1] that capped the weight, if used


@dataclass(frozen=True)
class Decision:
    obs: Observation
    bucket: str | None
    confidence: float
    intensity: float
    via: str  # "domain" | "shared" | "shape" | "none"


def _mean_shape(obs: list[Observation]) -> tuple[float, ...]:
    w = sum(o.bytes for o in obs)
    return tuple(sum(o.features[i] * o.bytes for o in obs) / w for i in range(N_FEATURES))


def enroll(name: str, weight: float, observations: Iterable[Observation]) -> Bucket:
    obs = list(observations)
    if not obs:
        raise ValueError(f"exemplar for {name!r} has no traffic")
    lengths = {o.window_s for o in obs}
    if len(lengths) != 1:
        raise ValueError(f"exemplar for {name!r} mixes window lengths {sorted(lengths)}")
    by_bytes: dict[str, int] = {}
    by_pkts: dict[str, int] = {}
    for o in obs:
        by_bytes[o.service] = by_bytes.get(o.service, 0) + o.bytes
        by_pkts[o.service] = by_pkts.get(o.service, 0) + o.packets
    tb, tp = sum(by_bytes.values()), sum(by_pkts.values())
    domains = {
        s for s in by_bytes
        if s != UNKNOWN and max(by_bytes[s] / tb, by_pkts[s] / tp) >= DOMAIN_SHARE
    }
    dominant = [o for o in obs if o.service in domains] or obs
    domain_shapes = {d: _mean_shape([o for o in obs if o.service == d]) for d in domains}
    return Bucket(
        name=name,
        weight=min(max(weight, 0.0), 1.0),
        domains=domains,
        shape=_mean_shape(dominant),
        domain_shapes=domain_shapes,
        window_s=lengths.pop(),
    )


def _d2(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.exp(-_d2(a, b) / (2 * SHAPE_SIGMA**2))


def intensity(weight: float, confidence: float, via: str) -> float:
    """Domain hits use weight directly; shape and shared hits scale by how far above their bar they are."""
    if via == "domain":
        scale = 1.0
    elif via == "shape":
        scale = (confidence - SHAPE_THRESHOLD) / (1.0 - SHAPE_THRESHOLD)
    elif via == "shared":
        scale = (confidence - SHARED_MARGIN) / (1.0 - SHARED_MARGIN)
    else:
        return 0.0
    return min(max(weight * scale, 0.0), 1.0)


def _shared(obs: Observation, hits: list[Bucket]) -> Decision:
    ranked = sorted(
        ((_d2(obs.features, b.domain_shapes.get(obs.service, b.shape)), b) for b in hits),
        key=lambda t: t[0],
    )
    (d_best, best), (d_next, _) = ranked[0], ranked[1]
    # P(best) between the two nearest, stable for any distances: sigmoid of the energy gap.
    conf = 1.0 / (1.0 + math.exp(-(d_next - d_best) / (2 * SHAPE_SIGMA**2)))
    if d_best > SHARED_MAX_D2 or conf < SHARED_MARGIN:
        return Decision(obs, None, conf, 0.0, "none")
    return Decision(obs, best.name, conf, intensity(best.weight, conf, "shared"), "shared")


def classify(obs: Observation, buckets: list[Bucket]) -> Decision:
    if obs.bytes < min_bytes(obs.window_s) or not buckets:
        return Decision(obs, None, 0.0, 0.0, "none")
    stale = sorted({b.window_s for b in buckets if b.window_s != obs.window_s})
    if stale:
        raise ValueError(f"buckets enrolled at window {stale} s, observation is {obs.window_s} s; re-enroll")
    if obs.service != UNKNOWN:
        hits = [b for b in buckets if obs.service in b.domains]
        if not hits:
            return Decision(obs, None, 0.0, 0.0, "none")
        if len(hits) > 1:
            return _shared(obs, hits)
        b = hits[0]
        return Decision(obs, b.name, 1.0, intensity(b.weight, 1.0, "domain"), "domain")
    sims = [(_similarity(obs.features, b.shape), b) for b in buckets]
    conf, b = max(sims, key=lambda t: (t[0], t[1].weight))
    if conf < SHAPE_THRESHOLD:
        return Decision(obs, None, conf, 0.0, "none")
    return Decision(obs, b.name, conf, intensity(b.weight, conf, "shape"), "shape")


def strongest(decisions: Iterable[Decision]) -> Decision | None:
    """At most one stimulus per window: the highest-intensity decision, if any is > 0."""
    best = max(decisions, key=lambda d: d.intensity, default=None)
    return best if best is not None and best.intensity > 0 else None


def duration_ms(level: float) -> int:
    """500 ms at threshold up to 2000 ms (the firmware ceiling) at full intensity."""
    return int(500 + 1500 * min(max(level, 0.0), 1.0))


def save(buckets: list[Bucket], path: Path) -> None:
    data = {
        b.name: {
            "weight": b.weight,
            "domains": sorted(b.domains),
            "shape": list(b.shape),
            "domain_shapes": {d: list(s) for d, s in sorted(b.domain_shapes.items())},
            "window_s": b.window_s,
            "tribe_drive": b.tribe_drive,
        }
        for b in buckets
    }
    path.write_text(json.dumps({"buckets": data}, indent=2) + "\n")


def load(path: Path) -> list[Bucket]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())["buckets"]
    return [
        Bucket(
            name=n,
            weight=v["weight"],
            domains=set(v["domains"]),
            shape=tuple(v["shape"]),
            domain_shapes={d: tuple(s) for d, s in v.get("domain_shapes", {}).items()},
            window_s=v.get("window_s", 10.0),  # stores written before this field were all 10 s
            tribe_drive=v.get("tribe_drive"),
        )
        for n, v in raw.items()
    ]
