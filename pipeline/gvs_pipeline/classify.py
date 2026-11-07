"""One-shot bucket classifier and stimulus intensity.

Enrollment: one labelled capture per bucket. Its dominant services become the
bucket's domain set; its byte-weighted mean flow shape becomes the bucket's prototype.

Classification of one Observation:
- named service in a bucket's domain set -> that bucket, confidence 1.
- named service in no bucket -> None. We know what it is and it was not enrolled.
- unnamed service (no DNS/SNI seen, e.g. ECH or a flow that started before capture)
  -> nearest shape prototype, kept only above SHAPE_THRESHOLD.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .flows import N_FEATURES, UNKNOWN, Observation

DOMAIN_SHARE = 0.10  # a service must carry >=10% of exemplar bytes to join the domain set
SHAPE_SIGMA = 0.15
SHAPE_THRESHOLD = 0.80
MIN_BYTES = 50_000  # below this a window's traffic is background noise, never stimulated


@dataclass
class Bucket:
    name: str
    weight: float  # 0..1, how strongly the user wants to be conditioned against this bucket
    domains: set[str] = field(default_factory=set)
    shape: tuple[float, ...] = (0.0,) * N_FEATURES


@dataclass(frozen=True)
class Decision:
    obs: Observation
    bucket: str | None
    confidence: float
    intensity: float
    via: str  # "domain" | "shape" | "none"


def enroll(name: str, weight: float, observations: Iterable[Observation]) -> Bucket:
    obs = list(observations)
    if not obs:
        raise ValueError(f"exemplar for {name!r} has no traffic")
    by_service: dict[str, int] = {}
    for o in obs:
        by_service[o.service] = by_service.get(o.service, 0) + o.bytes
    total = sum(by_service.values())
    domains = {s for s, b in by_service.items() if s != UNKNOWN and b / total >= DOMAIN_SHARE}
    dominant = [o for o in obs if o.service in domains] or obs
    w = sum(o.bytes for o in dominant)
    shape = tuple(sum(o.features[i] * o.bytes for o in dominant) / w for i in range(N_FEATURES))
    return Bucket(name=name, weight=min(max(weight, 0.0), 1.0), domains=domains, shape=shape)


def _similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    d2 = sum((x - y) ** 2 for x, y in zip(a, b))
    return math.exp(-d2 / (2 * SHAPE_SIGMA**2))


def intensity(weight: float, confidence: float, via: str) -> float:
    """Domain hits use weight directly; shape hits scale by how far above threshold they are."""
    if via == "domain":
        scale = 1.0
    elif via == "shape":
        scale = (confidence - SHAPE_THRESHOLD) / (1.0 - SHAPE_THRESHOLD)
    else:
        return 0.0
    return min(max(weight * scale, 0.0), 1.0)


def classify(obs: Observation, buckets: list[Bucket]) -> Decision:
    if obs.bytes < MIN_BYTES or not buckets:
        return Decision(obs, None, 0.0, 0.0, "none")
    if obs.service != UNKNOWN:
        hits = sorted((b for b in buckets if obs.service in b.domains), key=lambda b: -b.weight)
        if not hits:
            return Decision(obs, None, 0.0, 0.0, "none")
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
        b.name: {"weight": b.weight, "domains": sorted(b.domains), "shape": list(b.shape)}
        for b in buckets
    }
    path.write_text(json.dumps({"buckets": data}, indent=2) + "\n")


def load(path: Path) -> list[Bucket]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())["buckets"]
    return [
        Bucket(name=n, weight=v["weight"], domains=set(v["domains"]), shape=tuple(v["shape"]))
        for n, v in raw.items()
    ]
