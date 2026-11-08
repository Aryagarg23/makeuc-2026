"""Talk to the GVS device over Bluetooth LE (no USB, no WiFi).

  python ble.py status
  python ble.py stop
  python ble.py pulse 0.5 2000            # mA, ms; sine at 1 Hz, polarity 0
  python ble.py pulse 0.5 2000 --hz 1 --pol 1
  python ble.py watch 0.5 2000            # pulse, then poll status every 0.15 s until idle

Commands are the firmware's runCommand() lines, prefixed with the token from gvs/device.env.
Same limits as USB and HTTP: 2.0 mA, 3000 ms, 5 s cooldown, 30 per hour. Sine only from here:
DC isn't offered for use on a person (research/gvs.md: zero net charge).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

SVC = "6e7a0001-9c1b-4e5a-8f3d-67a5c0de0001"
CMD = "6e7a0002-9c1b-4e5a-8f3d-67a5c0de0001"
RESP = "6e7a0003-9c1b-4e5a-8f3d-67a5c0de0001"
ENV = Path(__file__).resolve().parents[1] / "device.env"


def token() -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith("GVS_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"no GVS_TOKEN in {ENV}")


async def send(client: BleakClient, tok: str, line: str) -> str:
    await client.write_gatt_char(CMD, f"{tok} {line}".encode(), response=True)
    for _ in range(20):  # the device runs the command on its next loop pass
        await asyncio.sleep(0.03)
        r = (await client.read_gatt_char(RESP)).decode(errors="replace")
        if r != "ready":
            return r
    return r


async def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("stop")
    for name in ("pulse", "watch"):
        p = sub.add_parser(name)
        p.add_argument("ma", type=float)
        p.add_argument("ms", type=int)
        p.add_argument("--hz", type=float, default=1.0)
        p.add_argument("--pol", type=int, choices=[0, 1], default=0)
    a = ap.parse_args()
    tok = token()
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == "GVS-zapper" or SVC in (ad.service_uuids or []), timeout=10.0)
    if dev is None:
        print("GVS-zapper not found over Bluetooth (powered? in range? Bluetooth allowed for this app?)")
        return 2
    async with BleakClient(dev) as client:
        if a.cmd == "status":
            print(await send(client, tok, "status"))
        elif a.cmd == "stop":
            print(await send(client, tok, "stop"))
        else:
            r = await send(client, tok, f"pulse {a.ma} {a.ms} {a.hz} {a.pol} sine")
            print(time.strftime("%H:%M:%S"), r)
            if a.cmd == "watch" and r.startswith("200"):
                t0 = time.time()
                while time.time() - t0 < a.ms / 1000 + 4:
                    st = json.loads(await send(client, tok, "status"))
                    print(f"  t={time.time()-t0:4.1f} {st['mode']:4s} relay={st['relay']:2d} "
                          f"cmd={st['cmd_ma']:.2f} meas={st['meas_ma']:.2f} hv={st['hv']:.1f} fault={st['fault']}")
                    if st["mode"] == "idle" and time.time() - t0 > 0.5:
                        break
                    await asyncio.sleep(0.15)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
