"""Keep one Bluetooth connection to the GVS device and relay commands from localhost.

Run it in macOS Terminal.app (which can be granted Bluetooth permission):
  ~/source/repos/makeuc-2026/pipeline/.venv/bin/python ~/source/repos/makeuc-2026/gvs/tools/ble_bridge.py

Then, from anywhere on this Mac:
  curl 'http://127.0.0.1:8765/cmd?line=status'
  curl 'http://127.0.0.1:8765/cmd?line=pulse%200.5%202000%201%200%20sine'

Listens on 127.0.0.1 only. Adds the token from gvs/device.env. DC steps are allowed for manual
threshold testing (the literature's standard 1-3 s GVS step) but only up to DC_MAX_MA; the pipeline
itself sends sine only. Ctrl-C stops it; the device keeps its own limits.
"""
from __future__ import annotations

import asyncio
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ble import CMD, RESP, SVC, token  # noqa: E402

PORT = 8765
DC_MAX_MA = 1.5  # manual DC steps only; above this use sine
loop = asyncio.new_event_loop()
state: dict = {"client": None, "lock": asyncio.Lock()}


async def ensure_client() -> BleakClient:
    c = state["client"]
    if c is not None and c.is_connected:
        return c
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == "GVS-zapper" or SVC in (ad.service_uuids or []), timeout=10.0)
    if dev is None:
        raise ConnectionError("GVS-zapper not found")
    c = BleakClient(dev)
    await c.connect()
    state["client"] = c
    print(time.strftime("%H:%M:%S"), "connected to", dev.address, flush=True)
    return c


async def run(line: str, tok: str) -> str:
    words = line.split()
    if words and words[0] == "pulse" and "dc" in words[1:]:
        try:
            if float(words[1]) > DC_MAX_MA:
                return f"400 bridge caps dc at {DC_MAX_MA} mA"
        except (IndexError, ValueError):
            return "400 bad pulse line"
    async with state["lock"]:
        c = await ensure_client()
        await c.write_gatt_char(CMD, f"{tok} {line}".encode(), response=True)
        r = "ready"
        for _ in range(20):
            await asyncio.sleep(0.03)
            r = (await c.read_gatt_char(RESP)).decode(errors="replace")
            if r != "ready":
                break
        return r


def main() -> int:
    tok = token()
    Thread(target=loop.run_forever, daemon=True).start()
    try:
        print(asyncio.run_coroutine_threadsafe(run("status", tok), loop).result(30), flush=True)
    except Exception as e:
        print("first connect failed:", e, flush=True)

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            line = urllib.parse.parse_qs(u.query).get("line", [""])[0]
            if u.path != "/cmd" or not line:
                self.send_response(404); self.end_headers(); return
            try:
                r = asyncio.run_coroutine_threadsafe(run(line, tok), loop).result(30)
                code = 200
            except Exception as e:
                state["client"] = None
                r, code = f"503 bridge: {e}", 503
            print(time.strftime("%H:%M:%S"), line, "->", r[:120], flush=True)
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write((r + "\n").encode())

        def log_message(self, *a):
            pass

    print(f"bridge on http://127.0.0.1:{PORT}/cmd?line=...", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
