"""CLI.

  enroll BUCKET CAPTURE.tsv --weight W     one-shot: add/replace a bucket from one labelled capture
      [--tribe CLIP.tribe.json --tribe-anchors NEUTRAL.tribe.json HIGH.tribe.json]
                                           cap W by TRIBE's predicted drive for the screen recording
  classify CAPTURE.tsv                     dry run over a saved capture, one line per window
  live [--gvs gvs/device.env --max-ma MA]  read tshark lines on stdin, stimulate on confirmed windows

Windows are --window s long and slide every --step s. A stimulus needs --confirm consecutive
steps agreeing on a bucket (gvs_pipeline/trigger.py).
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
from .trigger import Trigger


def _packets(lines: Iterable[str]) -> Iterable[Packet]:
    for line in lines:
        p = parse_line(line)
        if p is not None:
            yield p


def cmd_enroll(a: argparse.Namespace) -> int:
    with open(a.capture) as fh:
        obs = [o for w in windows(_packets(fh), a.window, a.step) for o in w]
    weight, drive = a.weight, None
    if a.tribe or a.tribe_anchors:
        if not (a.tribe and a.tribe_anchors):
            raise SystemExit("--tribe and --tribe-anchors go together")
        from . import tribe as T

        s, n, h = T.load_score(a.tribe), *(T.load_score(p) for p in a.tribe_anchors)
        drive = T.drive(s, n, h)
        weight = T.capped_weight(a.weight, s, n, h)
    b = C.enroll(a.bucket, weight, obs)
    b.tribe_drive = drive
    buckets = [x for x in C.load(a.store) if x.name != b.name] + [b]
    C.save(buckets, a.store)
    print(json.dumps({"bucket": b.name, "weight": b.weight, "user_weight": a.weight, "tribe_drive": drive,
                      "domains": sorted(b.domains),
                      "shape": [round(x, 3) for x in b.shape]}))
    return 0


def _run(lines: Iterable[str], a: argparse.Namespace, out: TextIO, esp=None) -> None:
    buckets = C.load(a.store)
    stale = sorted({b.name for b in buckets if b.window_s != a.window})
    if stale:
        raise SystemExit(f"buckets {stale} were enrolled at a different --window; re-enroll at {a.window} s")
    trig = Trigger(a.step, a.confirm)
    for obs in windows(_packets(lines), a.window, a.step):
        t = obs[0].window_start
        best = C.strongest(C.classify(o, buckets) for o in obs)
        fired = trig.update(t, best)
        rec: dict = {"window": t, "services": len(obs), "fired": fired is not None}
        if best is not None:
            ms = C.duration_ms(best.intensity)
            rec.update(bucket=best.bucket, service=best.obs.service, via=best.via,
                       confidence=round(best.confidence, 3), intensity=round(best.intensity, 3), ms=ms)
            if fired is not None and esp is not None:
                rec["gvs"] = esp.stim(best.bucket, best.intensity, ms)
        out.write(json.dumps(rec) + "\n")
        out.flush()


def cmd_classify(a: argparse.Namespace) -> int:
    with open(a.capture) as fh:
        _run(fh, a, sys.stdout)
    return 0


def cmd_live(a: argparse.Namespace) -> int:
    esp = None
    if a.gvs:
        from .gvs_link import Gvs

        if a.max_ma is None:
            raise SystemExit("--gvs needs --max-ma: the ceiling you titrated to on-head (research/gvs.md)")
        esp = Gvs.from_env(a.gvs, a.max_ma, a.hz)
    try:
        _run(sys.stdin, a, sys.stdout, esp)
    finally:
        if esp is not None:
            esp.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gvs_pipeline")
    ap.add_argument("--store", type=Path, default=Path("prototypes.json"))
    ap.add_argument("--window", type=float, default=3.0, help="window length, s")
    ap.add_argument("--step", type=float, default=1.0, help="window slide, s")
    ap.add_argument("--confirm", type=int, default=2, help="consecutive agreeing steps before a stimulus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enroll")
    e.add_argument("bucket")
    e.add_argument("capture")
    e.add_argument("--weight", type=float, required=True)
    e.add_argument("--tribe", type=Path, help="tribe/score_clip.py output for this bucket's screen recording")
    e.add_argument("--tribe-anchors", type=Path, nargs=2, metavar=("NEUTRAL", "HIGH"))
    e.set_defaults(fn=cmd_enroll)
    c = sub.add_parser("classify")
    c.add_argument("capture")
    c.set_defaults(fn=cmd_classify)
    l = sub.add_parser("live")
    l.add_argument("--gvs", type=Path, help="device env file with GVS_URL, GVS_TOKEN (gvs/tools/make_secrets.sh); omit for dry run")
    l.add_argument("--max-ma", type=float, help="current at intensity 1, mA (<= firmware FW_MAX_MA 2.0)")
    l.add_argument("--hz", type=float, default=1.0, help="sine frequency, 0.5-2 Hz")
    l.set_defaults(fn=cmd_live)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
