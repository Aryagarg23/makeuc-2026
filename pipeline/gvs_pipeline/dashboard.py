"""Local dashboard for `live`: see which services are moving packets right now, and choose which ones
start the nausea (rules.py). Standard library only.

  GET  /            the page (dashboard.html)
  GET  /api/state   services in the latest window, recent services, rules, buckets, recent stimuli
  POST /api/rules   replace the rules (JSON, validated by rules.Rules.parse); returns the new state

Binds to 127.0.0.1 unless told otherwise. Off loopback (the UNO Q's hotspot, which friends join for fun mode)
a key is required on every /api call (header X-Dashboard-Key; the page reads it from the URL's #key=...), so
people on the same network can neither see the traffic nor change what fires.
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import classify as C
from .flows import UNKNOWN
from .rules import Live, RuleError

PAGE = Path(__file__).with_name("dashboard.html")
SEEN_S = 120.0  # how long a service stays in the "recently seen" list after its last packet window


class State:
    def __init__(self, live: Live, buckets: list[C.Bucket], armed: bool, max_ma: float | None,
                 window_s: float, step_s: float) -> None:
        self.live, self.buckets = live, buckets
        self.config = {"armed": armed, "max_ma": max_ma, "window_s": window_s, "step_s": step_s}
        self._lock = threading.Lock()
        self._now: list[dict] = []
        self._seen: dict[str, dict] = {}
        self._stims: deque[dict] = deque(maxlen=20)
        self._last_t: float | None = None

    def note(self, t: float, decisions: list[C.Decision], rec: dict) -> None:
        """Called by the packet loop once per window."""
        rows = []
        for d in sorted(decisions, key=lambda d: -d.obs.bytes):
            o = d.obs
            rows.append({"service": o.service if o.service != UNKNOWN else f"unnamed {o.server}",
                         "named": o.service != UNKNOWN, "kbps": round(o.bytes / o.window_s / 1000, 1),
                         "bucket": d.bucket, "via": d.via, "intensity": round(d.intensity, 3)})
        with self._lock:
            self._last_t = t
            self._now = rows
            for r in rows:
                if r["named"]:
                    s = self._seen.setdefault(r["service"], {"service": r["service"], "peak_kbps": 0.0})
                    s["last"] = t
                    s["peak_kbps"] = max(s["peak_kbps"], r["kbps"])
            for k in [k for k, v in self._seen.items() if t - v["last"] > SEEN_S]:
                del self._seen[k]
            if rec.get("fired"):
                self._stims.appendleft({"t": t, "wall": time.time(), **{k: rec.get(k) for k in
                                        ("service", "bucket", "via", "intensity", "ms", "gvs")}})

    def snapshot(self) -> dict:
        rules = self.live.get()
        with self._lock:
            return {
                "config": self.config, "window": self._last_t, "now": list(self._now),
                "server_time": time.time(),  # ages are measured on the server's clock: the UNO Q's is not synced
                "seen": sorted(self._seen.values(), key=lambda s: -s["peak_kbps"]),
                "stims": list(self._stims), "rules": rules.to_json(),
                "buckets": [{"name": b.name, "enrolled_weight": b.weight, "domains": sorted(b.domains)}
                            for b in self.buckets],
            }


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def key_for(host: str, path: Path) -> str | None:
    """No key on loopback. Otherwise a key kept in `path`, created once, so the dashboard link stays the same."""
    if host in LOOPBACK:
        return None
    if not path.exists():
        path.write_text(secrets.token_urlsafe(9) + "\n")
        path.chmod(0o600)
    return path.read_text().strip()


def serve(state: State, host: str = "127.0.0.1", port: int = 8080, key: str | None = None) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def _locked(self) -> bool:
            if key is None or hmac.compare_digest(self.headers.get("X-Dashboard-Key", ""), key):
                return False
            self._json(401, {"error": "locked: open the dashboard link that includes #key=..."})
            return True

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: object) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self) -> None:
            if self.path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                if not self._locked():
                    self._json(200, state.snapshot())
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != "/api/rules":
                return self._json(404, {"error": "not found"})
            if self._locked():
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > 64_000:
                    raise RuleError("rules too large")
                state.live.set(json.loads(self.rfile.read(n) or b"{}"))
            except (RuleError, json.JSONDecodeError, KeyError) as e:
                return self._json(400, {"error": str(e)})
            self._json(200, state.snapshot())

        def log_message(self, *a) -> None:
            pass

    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
