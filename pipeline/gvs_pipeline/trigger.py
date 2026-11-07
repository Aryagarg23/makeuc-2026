"""Turn per-step decisions into stimuli.

Sliding windows give a decision every step. A stimulus fires only when the same bucket wins
CONFIRM consecutive steps, then nothing fires for REFRACTORY_S. Two agreeing steps cost one
step of latency and stop a single odd window (one photo in a chat) from firing; the refractory
period matches the firmware cooldown so the link never sends a stim the ESP32 would refuse.
"""
from __future__ import annotations

from .classify import Decision

CONFIRM = 2
REFRACTORY_S = 5.0  # esp32/gvs_controller/safety.h COOLDOWN_MS


class Trigger:
    def __init__(self, step_s: float, confirm: int = CONFIRM, refractory_s: float = REFRACTORY_S) -> None:
        if confirm < 1:
            raise ValueError("confirm must be >= 1")
        self.step_s = step_s
        self.confirm = confirm
        self.refractory_s = refractory_s
        self._bucket: str | None = None
        self._last_t: float | None = None
        self._streak = 0
        self._quiet_until = float("-inf")

    def update(self, t: float, best: Decision | None) -> Decision | None:
        """Feed the strongest decision of the window starting at t (None = nothing). Returns it if it fires."""
        consecutive = self._last_t is not None and abs(t - self._last_t - self.step_s) < 1e-6
        self._last_t = t
        if best is None:
            self._bucket, self._streak = None, 0
            return None
        if consecutive and best.bucket == self._bucket:
            self._streak += 1
        else:
            self._bucket, self._streak = best.bucket, 1
        if self._streak < self.confirm or t < self._quiet_until:
            return None
        self._streak = 0
        self._quiet_until = t + self.refractory_s
        return best
