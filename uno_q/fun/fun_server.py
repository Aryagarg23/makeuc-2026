#!/usr/bin/env python3
"""Fun mode on the UNO Q: a steering website on its own WiFi hotspot, driving the GVS over Bluetooth.

People join the hotspot (its password is in uno_q/fun/hotspot_pass), open http://10.42.0.1:8080/ and steer the tilt with
the same page as the Mac relay (gvs/tools/live.html). This server:
  /            the page
  /live?ma=x   fire-and-forget live update (BLE write without response), also drawn on the LED matrix
  /cmd?line=   one firmware command line, reply = the firmware's "<code> <msg>" (or status JSON)
Limits are the firmware's (dead-man 1 s, 30 min/h of current, 2.0 mA, slew). The UNO Q feeds the dead-man
itself at 10 Hz (heartbeat) and drops to 0 mA if the page is quiet for 1.5 s; STOP ends the heartbeat.

Mains: a USB-tethered board on a charging Mac ties the electrodes to wall power. This server does not
check for it (user's call, 2026-11-08); the page warns while the board reports "usb": true.

Runs with the system python3 plus bleak/dbus-fast unpacked into ~/gvs/lib (no internet on the board).
"""
from __future__ import annotations

import asyncio
import json
import socket
import struct
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from bleak import BleakClient, BleakScanner  # noqa: E402

PORT = 8080
SVC = "6e7a0001-9c1b-4e5a-8f3d-67a5c0de0001"
CMD = "6e7a0002-9c1b-4e5a-8f3d-67a5c0de0001"
RESP = "6e7a0003-9c1b-4e5a-8f3d-67a5c0de0001"
LIVE_MAX_MA = 2.0
DC_MAX_MA = 1.5
ROUTER = "/var/run/arduino-router.sock"
TOKEN = ""  # read from ./token in main()

loop = asyncio.new_event_loop()
state: dict = {"client": None, "lock": None, "status": {}, "status_t": 0.0, "matrix_t": 0.0,
               "target": 0.0, "page_t": 0.0, "hb_on": False}
HEARTBEAT_S = 0.1   # the UNO Q itself feeds the board's 1 s dead-man, 10x a second
PAGE_SILENT_S = 1.5  # page quiet this long -> target 0 mA, session kept open (no current without a person)


# ---------- minimal msgpack (only what msgpack-rpc to the Arduino Router needs) ----------
def mp_pack(o) -> bytes:
    if o is None:
        return b"\xc0"
    if o is True:
        return b"\xc3"
    if o is False:
        return b"\xc2"
    if isinstance(o, int):
        if 0 <= o < 128:
            return bytes([o])
        if -32 <= o < 0:
            return struct.pack("b", o)
        return b"\xd3" + struct.pack(">q", o)
    if isinstance(o, float):
        return b"\xca" + struct.pack(">f", o)  # float32: the sketch's handlers take float
    if isinstance(o, str):
        b = o.encode()
        return (bytes([0xA0 | len(b)]) if len(b) < 32 else b"\xd9" + bytes([len(b)])) + b
    if isinstance(o, (list, tuple)):
        return bytes([0x90 | len(o)]) + b"".join(mp_pack(x) for x in o)
    raise TypeError(type(o))


def mp_unpack(b: bytes, i: int = 0):
    t = b[i]
    if t <= 0x7F:
        return t, i + 1
    if 0x80 <= t <= 0x8F:
        n, i, d = t & 0x0F, i + 1, {}
        for _ in range(n):
            k, i = mp_unpack(b, i)
            v, i = mp_unpack(b, i)
            d[k] = v
        return d, i
    if 0x90 <= t <= 0x9F:
        n, i, out = t & 0x0F, i + 1, []
        for _ in range(n):
            v, i = mp_unpack(b, i)
            out.append(v)
        return out, i
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[i + 1:i + 1 + n].decode(errors="replace"), i + 1 + n
    if t >= 0xE0:
        return t - 256, i + 1
    simple = {0xC0: None, 0xC2: False, 0xC3: True}
    if t in simple:
        return simple[t], i + 1
    fmt = {0xCA: ">f", 0xCB: ">d", 0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q",
           0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q"}
    if t in fmt:
        n = struct.calcsize(fmt[t])
        return struct.unpack(fmt[t], b[i + 1:i + 1 + n])[0], i + 1 + n
    if t in (0xD9, 0xDA):
        ln = 1 if t == 0xD9 else 2
        n = int.from_bytes(b[i + 1:i + 1 + ln], "big")
        s = i + 1 + ln
        return b[s:s + n].decode(errors="replace"), s + n
    raise ValueError(f"msgpack type 0x{t:02x} not handled")


def matrix(method: str, params: list) -> None:
    """Best effort: the LED matrix is decoration; never let it block or break steering."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.connect(ROUTER)
            s.sendall(mp_pack([0, 7, method, params]))
            s.recv(256)
    except OSError:
        pass


# ---------- BLE ----------
def _dropped(_client) -> None:
    print(time.strftime("%H:%M:%S"), "BLE link dropped", flush=True)
    state["client"] = None


async def ensure_client() -> BleakClient:
    c = state["client"]
    if c is not None and c.is_connected:
        return c
    known = HERE / "board_addr"
    # Fast path: reconnect straight to the board we already know (no 10 s scan). Range drops are the
    # common case, and the board starts advertising again the moment it loses us.
    if known.exists():
        try:
            c = BleakClient(known.read_text().strip(), disconnected_callback=_dropped, timeout=6.0)
            await c.connect()
            state["client"] = c
            print(time.strftime("%H:%M:%S"), "reconnected", flush=True)
            return c
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "direct reconnect failed:", e, flush=True)
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == "GVS-zapper" or SVC in (ad.service_uuids or []), timeout=8.0)
    if dev is None:
        raise ConnectionError("GVS-zapper not found (powered? in range? Mac relay still connected?)")
    c = BleakClient(dev, disconnected_callback=_dropped)
    await c.connect()
    state["client"] = c
    known.write_text(dev.address)
    print(time.strftime("%H:%M:%S"), "connected to", dev.address, flush=True)
    return c


async def keepalive() -> None:
    """Reconnect in the background so the link is up before the next drag, not after it."""
    while True:
        await asyncio.sleep(2.0)
        c = state["client"]
        if c is None or not c.is_connected:
            try:
                async with state["lock"]:
                    await ensure_client()
            except Exception as e:
                print(time.strftime("%H:%M:%S"), "keepalive:", e, flush=True)


async def run(line: str) -> str:
    async with state["lock"]:
        c = await ensure_client()
        await c.write_gatt_char(CMD, f"{TOKEN} {line}".encode(), response=True)
        r = "ready"
        for _ in range(20):
            await asyncio.sleep(0.03)
            r = (await c.read_gatt_char(RESP)).decode(errors="replace")
            if r != "ready":
                break
        if line == "status":
            try:
                state["status"], state["status_t"] = json.loads(r), time.time()
            except ValueError:
                pass
        return r


async def live(ma: float) -> str:
    ma = max(-LIVE_MAX_MA, min(LIVE_MAX_MA, ma))
    async with state["lock"]:
        c = await ensure_client()
        await c.write_gatt_char(CMD, f"{TOKEN} live {ma:.3f}".encode(), response=False)
    return f"sent live {ma:.3f}"


def call(coro, timeout: float):
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)


def mains_risk() -> str | None:
    """No Mac-side check (removed 2026-11-08 at the user's request: they keep the Mac off its charger while
    the board is on USB). The page shows a warning whenever the board reports USB attached."""
    return None


def mains_risk_cached() -> bool:
    return False  # see mains_risk()


async def heartbeat() -> None:
    """Send the current target to the board every HEARTBEAT_S while armed. The page only moves the target,
    so WiFi/page jitter never reaches the board's dead-man; only a real Bluetooth loss can trip it."""
    tick = 0
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        if not state["hb_on"]:
            continue
        tick += 1
        t = state["target"] if time.time() - state["page_t"] < PAGE_SILENT_S else 0.0
        if t != 0.0 and mains_risk_cached():
            t = 0.0
        try:
            await live(t)
        except Exception as e:
            if tick % 20 == 0:
                print(time.strftime("%H:%M:%S"), "heartbeat:", e, flush=True)
            state["client"] = None
        if tick % 2 == 0:
            matrix("tilt", [t / LIVE_MAX_MA])
        if tick % 50 == 0:  # refresh the cached status every ~5 s for the mains rule
            try:
                await run("status")
            except Exception:
                pass


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/live.html"):
            return self._send(200, (HERE / "live.html").read_bytes(), "text/html; charset=utf-8")
        try:
            if u.path == "/live" and "ma" in q:
                ma = float(q["ma"][0])
                if ma != 0 and (why := mains_risk()):
                    return self._send(200, (why + "\n").encode())
                state["target"] = max(-LIVE_MAX_MA, min(LIVE_MAX_MA, ma))
                state["page_t"] = time.time()
                state["hb_on"] = True
                c = state["client"]
                if c is None or not c.is_connected:
                    return self._send(200, b"503 bluetooth reconnecting\n")
                return self._send(200, f"sent live {state['target']:.3f}\n".encode())
            line = q.get("line", [""])[0]
            if u.path != "/cmd" or not line:
                return self._send(404, b"not found\n")
            words = line.split()
            if words[0] == "stop":
                state["hb_on"] = False
                state["target"] = 0.0
            if words[0] in ("pulse", "live", "boost") and (why := mains_risk()):
                return self._send(200, (why + "\n").encode())
            if words[0] == "pulse" and "dc" in words[1:]:
                if float(words[1]) > DC_MAX_MA:
                    return self._send(200, f"400 dc capped at {DC_MAX_MA} mA\n".encode())
            r = call(run(line), 30)
            if words[0] == "stop":
                matrix("tilt", [0.0])
            return self._send(200, (r + "\n").encode())
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "request failed:", repr(e), flush=True)
            state["client"] = None
            return self._send(503, f"503 uno-q: {e}\n".encode())

    def log_message(self, *a):
        pass


def main() -> int:
    global TOKEN
    TOKEN = (HERE / "token").read_text().strip()

    async def mk_lock():
        state["lock"] = asyncio.Lock()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    asyncio.run_coroutine_threadsafe(mk_lock(), loop).result(5)
    asyncio.run_coroutine_threadsafe(keepalive(), loop)
    asyncio.run_coroutine_threadsafe(heartbeat(), loop)
    matrix("tilt", [0.0])
    try:
        print("board:", call(run("status"), 30), flush=True)
    except Exception as e:
        print("first connect failed:", e, flush=True)
    print(f"fun mode on http://0.0.0.0:{PORT}/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
