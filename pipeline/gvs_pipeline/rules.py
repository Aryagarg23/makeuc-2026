"""Live-editable rules on top of the enrolled buckets: which packets start the nausea.

rules.json = {"paused": false,
              "services": {"tiktok.com": 0.8, "whatsapp.net": 0},   service -> weight; 0 = never
              "buckets":  {"ig_reels": {"on": true, "weight": 0.9}}}  per enrolled bucket

How a window's observation is decided with rules in force:
- service rule with weight > 0 -> that service fires at that weight (via "rule"), even if it was never enrolled.
- service rule with weight 0   -> never stimulated, whatever the buckets say (the DMs case).
- no service rule              -> the enrolled buckets decide (classify.py), with each bucket's weight replaced
                                  by its rule weight, and switched-off buckets removed.
- paused                       -> decisions are still made and shown, nothing fires.
The rate floor (classify.min_bytes) applies to rules too: a quiet service never fires.
Weights are clamped to [0, 1]. Current is weight x --max-ma, and the firmware caps it again, so no rule can
ask for more than the ceiling set on the command line.
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import classify as C
from .flows import UNKNOWN, Observation

_SERVICE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


class RuleError(ValueError):
    pass


def _weight(v: object, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise RuleError(f"{what}: weight must be a number")
    if not 0.0 <= float(v) <= 1.0:
        raise RuleError(f"{what}: weight must be between 0 and 1")
    return float(v)


@dataclass(frozen=True)
class Rules:
    paused: bool = False
    services: dict[str, float] = field(default_factory=dict)
    buckets: dict[str, tuple[bool, float]] = field(default_factory=dict)  # name -> (on, weight)

    @staticmethod
    def parse(raw: dict, known_buckets: set[str] | None = None) -> "Rules":
        """Validate a rules document. Unknown bucket names are refused when known_buckets is given."""
        if not isinstance(raw, dict):
            raise RuleError("rules must be an object")
        paused = raw.get("paused", False)
        if not isinstance(paused, bool):
            raise RuleError("paused must be true or false")
        services = {}
        for s, w in (raw.get("services") or {}).items():
            s = str(s).strip().lower()
            if not _SERVICE.match(s):
                raise RuleError(f"{s!r} is not a domain like tiktok.com")
            services[s] = _weight(w, s)
        buckets = {}
        for name, v in (raw.get("buckets") or {}).items():
            if known_buckets is not None and name not in known_buckets:
                raise RuleError(f"no enrolled bucket called {name!r}")
            if not isinstance(v, dict) or not isinstance(v.get("on", True), bool):
                raise RuleError(f"{name}: expected {{'on': bool, 'weight': number}}")
            buckets[name] = (v.get("on", True), _weight(v["weight"], name))
        return Rules(paused, services, buckets)

    def to_json(self) -> dict:
        return {"paused": self.paused, "services": dict(sorted(self.services.items())),
                "buckets": {n: {"on": on, "weight": w} for n, (on, w) in sorted(self.buckets.items())}}

    def effective(self, buckets: list[C.Bucket]) -> list[C.Bucket]:
        """Enrolled buckets with rule weights applied and switched-off buckets removed."""
        out = []
        for b in buckets:
            on, w = self.buckets.get(b.name, (True, b.weight))
            if on:
                out.append(replace(b, weight=w))
        return out

    def decide(self, obs: Observation, buckets: list[C.Bucket]) -> C.Decision:
        w = self.services.get(obs.service) if obs.service != UNKNOWN else None
        if w is None:
            return C.classify(obs, self.effective(buckets))
        if w == 0 or obs.bytes < C.min_bytes(obs.window_s):
            return C.Decision(obs, None, 0.0, 0.0, "none")
        return C.Decision(obs, f"rule:{obs.service}", 1.0, w, "rule")


def load(path: Path, known_buckets: set[str] | None = None) -> Rules:
    if not path.exists():
        return Rules()
    return Rules.parse(json.loads(path.read_text()), known_buckets)


def save(rules: Rules, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rules.to_json(), indent=2) + "\n")
    os.replace(tmp, path)  # atomic: a reader never sees half a file


class Live:
    """Thread-safe holder: the dashboard writes, the packet loop reads once per window."""

    def __init__(self, path: Path, known_buckets: set[str]) -> None:
        self.path, self.known = path, known_buckets
        self._lock = threading.Lock()
        self._rules = load(path, known_buckets)

    def get(self) -> Rules:
        with self._lock:
            return self._rules

    def set(self, raw: dict) -> Rules:
        r = Rules.parse(raw, self.known)
        with self._lock:
            save(r, self.path)
            self._rules = r
        return r
