"""CLI.

  enroll BUCKET CAPTURE.tsv --weight W     one-shot: add/replace a bucket from one labelled capture
  classify CAPTURE.tsv                     dry run over a saved capture, one line per window
  live [--esp32 PORT]                      read tshark lines on stdin, stimulate per window
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, TextIO

from . import classify as C
from .flows import windows
from .packets import Packet, parse_line


def _packets(lines: Iterable[str]) -> Iterable[Packet]:
    for line in lines:
        p = parse_line(line)
        if p is not None:
            yield p


def cmd_enroll(a: argparse.Namespace) -> int:
    with open(a.capture) as fh:
        obs = [o for w in windows(_packets(fh), a.window) for o in w]
    b = C.enroll(a.bucket, a.weight, obs)
    buckets = [x for x in C.load(a.store) if x.name != b.name] + [b]
    C.save(buckets, a.store)
    print(json.dumps({"bucket": b.name, "weight": b.weight, "domains": sorted(b.domains),
                      "shape": [round(x, 3) for x in b.shape]}))
    return 0


def _run(lines: Iterable[str], a: argparse.Namespace, out: TextIO, esp=None) -> None:
    buckets = C.load(a.store)
    for obs in windows(_packets(lines), a.window):
        best = C.strongest(C.classify(o, buckets) for o in obs)
        rec: dict = {"window": obs[0].window_start if obs else None, "services": len(obs)}
        if best is not None:
            ms = C.duration_ms(best.intensity)
            rec.update(bucket=best.bucket, service=best.obs.service, via=best.via,
                       confidence=round(best.confidence, 3), intensity=round(best.intensity, 3), ms=ms)
            if esp is not None:
                rec["esp32"] = esp.stim(best.bucket, best.intensity, ms)
        out.write(json.dumps(rec) + "\n")
        out.flush()


def cmd_classify(a: argparse.Namespace) -> int:
    with open(a.capture) as fh:
        _run(fh, a, sys.stdout)
    return 0


def cmd_live(a: argparse.Namespace) -> int:
    esp = None
    if a.esp32:
        from .esp32_link import Esp32

        esp = Esp32.open(a.esp32)
        print(json.dumps({"esp32_arm": esp.arm()}), flush=True)
    try:
        _run(sys.stdin, a, sys.stdout, esp)
    finally:
        if esp is not None:
            esp.stop()
            esp.disarm()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gvs_pipeline")
    ap.add_argument("--store", type=Path, default=Path("prototypes.json"))
    ap.add_argument("--window", type=float, default=10.0)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enroll")
    e.add_argument("bucket")
    e.add_argument("capture")
    e.add_argument("--weight", type=float, required=True)
    e.set_defaults(fn=cmd_enroll)
    c = sub.add_parser("classify")
    c.add_argument("capture")
    c.set_defaults(fn=cmd_classify)
    l = sub.add_parser("live")
    l.add_argument("--esp32", help="serial port, e.g. /dev/cu.usbmodem1101; omit for dry run")
    l.set_defaults(fn=cmd_live)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
