"""Newline-JSON client for esp32/gvs_controller over USB serial."""
from __future__ import annotations

import json
import time
from typing import Protocol

REARM_EVERY_S = 300.0  # firmware arming expires after 600 s
# Replies that mean someone outside this process stopped the device. The link halts and never re-arms.
HALT_REASONS = {"estop", "not_armed"}


class LineIO(Protocol):
    def write(self, data: bytes) -> int | None: ...
    def readline(self) -> bytes: ...


class Esp32:
    def __init__(self, io: LineIO, clock=time.monotonic) -> None:
        self.io = io
        self.clock = clock
        self._armed_at: float | None = None
        self.halted: str | None = None

    @classmethod
    def open(cls, port: str) -> "Esp32":
        import serial

        return cls(serial.Serial(port, 115200, timeout=3))

    def call(self, msg: dict) -> dict:
        self.io.write((json.dumps(msg, separators=(",", ":")) + "\n").encode())
        line = self.io.readline()
        if not line:
            raise TimeoutError(f"no reply to {msg.get('cmd')}")
        return json.loads(line)

    def arm(self) -> dict:
        reply = self.call({"cmd": "arm"})
        if not reply.get("ok"):
            self.halted = reply.get("reason", "arm_refused")
        self._armed_at = self.clock()
        return reply

    def stim(self, bucket: str, level: float, ms: int) -> dict:
        if self.halted is not None:
            return {"ok": False, "reason": "halted", "cause": self.halted}
        if self._armed_at is None or self.clock() - self._armed_at >= REARM_EVERY_S:
            self.arm()
            if self.halted is not None:
                return {"ok": False, "reason": "halted", "cause": self.halted}
        level = min(max(float(level), 0.0), 1.0)
        reply = self.call({"cmd": "stim", "bucket": bucket, "intensity": round(level, 4), "ms": int(ms)})
        if not reply.get("ok") and reply.get("reason") in HALT_REASONS:
            self.halted = reply["reason"]
        return reply

    def stop(self) -> dict:
        return self.call({"cmd": "stop"})

    def disarm(self) -> dict:
        self._armed_at = None
        return self.call({"cmd": "disarm"})
