"""HTTP client for gvs/firmware/gvs_controller (XIAO ESP32-C3 current sink with relay polarity).

Every stimulus is a zero-mean sine burst of whole cycles (research/gvs.md §7 F2): the firmware's
DC mode is never used. Current is level x max_ma, where max_ma is the ceiling you reached in
the on-head titration (start 0.5 mA, 0.25 mA steps), never above the firmware's FW_MAX_MA.

Replies that mean a person or the device stopped things (bad token, latched fault) halt the
link for good; busy and cooldown are skipped stimuli, not halts.

Two transports:
- WiFi HTTP straight to the board (`Gvs(url, token, ...)`, `/pulse?...`), when the firmware has an SSID.
- The Bluetooth relay on this Mac (`Gvs.relay(...)`, gvs/tools/ble_bridge.py), which adds the token and
  answers the firmware's own "<code> <msg>" line in the body. The relay refuses current with
  "403 refused: ..." while the Mac is on its charger and the board is on USB; that is a skip, not a halt.
"""
from __future__ import annotations

import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

FW_MAX_MA = 2.0  # gvs_controller.ino FW_MAX_MA
FW_MAX_MS = 3000  # gvs_controller.ino MAX_MS
FW_MIN_MS = 600  # gvs_controller.ino 2 * RAMP_MS
HALT_STATUS = {403: "bad_token", 423: "faulted"}
RELAY_URL = "http://127.0.0.1:8765"
SKIP_STATUS = {409: "busy", 429: "cooldown"}

# (url) -> (http status, body); raises OSError when unreachable
Getter = Callable[[str], "tuple[int, str]"]


def _http_get(url: str, timeout: float = 2.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def whole_cycles_ms(ms: float, hz: float) -> int:
    """Nearest whole number of sine cycles to ms, within the firmware's [FW_MIN_MS, FW_MAX_MS]."""
    period = 1000.0 / hz
    lo = max(1, -(-FW_MIN_MS // period))  # ceil
    hi = FW_MAX_MS // period
    if lo > hi:
        raise ValueError(f"no whole number of {hz} Hz cycles fits {FW_MIN_MS}-{FW_MAX_MS} ms")
    n = min(max(round(ms / period), lo), hi)
    return int(round(n * period))


def load_env(path: Path) -> dict[str, str]:
    out = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class Gvs:
    def __init__(self, base_url: str, token: str, max_ma: float, hz: float = 1.0, get: Getter = _http_get) -> None:
        if not 0 < max_ma <= FW_MAX_MA:
            raise ValueError(f"max_ma must be in (0, {FW_MAX_MA}]")
        if not 0.5 <= hz <= 2.0 or abs(1000.0 / hz - round(1000.0 / hz)) > 1e-9:
            # The firmware takes ms as an integer; whole cycles need a whole-millisecond period.
            raise ValueError("hz must be in [0.5, 2.0] with a whole-millisecond period (0.5, 1, 1.25, 2, ...)")
        whole_cycles_ms(1000, hz)
        self.base = base_url.rstrip("/")
        self.token = token
        self.max_ma = max_ma
        self.hz = hz
        self.get = get
        self.halted: str | None = None
        self._pol = 0

    @classmethod
    def relay(cls, max_ma: float, hz: float = 1.0, url: str = RELAY_URL, get: Getter = _http_get) -> "Gvs":
        return cls(url, None, max_ma, hz, get=get)

    @classmethod
    def from_env(cls, path: Path, max_ma: float, hz: float = 1.0) -> "Gvs":
        e = load_env(path)
        return cls(e["GVS_URL"], e["GVS_TOKEN"], max_ma, hz)

    def _call(self, path: str, **params) -> tuple[int, str]:
        if self.token is None:  # relay: one firmware command line; the code is the body's first word
            line = "stop" if path == "/stop" else (
                f"pulse {params['ma']} {params['ms']} {params['hz']} {params['pol']} {params['mode']}")
            code, body = self.get(f"{self.base}/cmd?{urllib.parse.urlencode({'line': line})}")
            head, _, rest = body.strip().partition(" ")
            if head.isdigit():
                return int(head), rest
            return code, body
        q = urllib.parse.urlencode({**params, "token": self.token})
        return self.get(f"{self.base}{path}?{q}")

    def stim(self, bucket: str, level: float, ms: int) -> dict:
        if self.halted is not None:
            return {"ok": False, "reason": "halted", "cause": self.halted}
        level = min(max(float(level), 0.0), 1.0)
        ma = math.floor(self.max_ma * level * 1000) / 1000  # floor: rounding up could exceed max_ma
        dur = whole_cycles_ms(ms, self.hz)
        try:
            code, body = self._call("/pulse", ma=ma, ms=dur, mode="sine", hz=self.hz, pol=self._pol)
        except OSError as e:
            return {"ok": False, "reason": "unreachable", "detail": str(e)}
        rec = {"bucket": bucket, "ma": ma, "ms": dur, "hz": self.hz, "pol": self._pol, "body": body.strip()}
        if code == 200:
            self._pol ^= 1  # alternate which side leads, so successive bursts start on opposite sides
            return {"ok": True, **rec}
        if self.token is None and code == 403:
            return {"ok": False, "reason": "mains_risk", **rec}
        if self.token is None and code == 503:
            return {"ok": False, "reason": "unreachable", **rec}
        if code in HALT_STATUS:
            self.halted = HALT_STATUS[code]
            return {"ok": False, "reason": "halted", "cause": self.halted, **rec}
        if code == 429 and body.strip() in ("cooldown", "hourly_limit"):
            return {"ok": False, "reason": body.strip(), **rec}
        return {"ok": False, "reason": SKIP_STATUS.get(code, f"http_{code}"), **rec}

    def stop(self) -> dict:
        try:
            code, body = self._call("/stop")
        except OSError as e:
            return {"ok": False, "reason": "unreachable", "detail": str(e)}
        return {"ok": code == 200, "body": body.strip()}
