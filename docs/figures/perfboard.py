"""The perfboard, front view, as a clean SVG: every part, bridge and jumper, in light and dark.

  python3 docs/figures/perfboard.py docs/figures        writes perfboard.svg and perfboard-dark.svg

Replaces the old raster handoff picture (gvs/pictures/full_front.png). Everything comes from
gvs/board/layout.py, the layout that was soldered, so the board, the schematic and the SPICE model share one
source. Colours are the site's tokens: red-orange for the HV bus and the current path, blue for signals,
ink for the rest. Part values are printed on the parts; jumpers are tagged J1 to J13 as in docs/HARDWARE.md.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gvs" / "board"))
import layout as L  # noqa: E402

FONT = "Space Grotesk, Inter, system-ui, sans-serif"
THEMES = {
    "light": dict(paper="#eae4d6", board="#ddd5c0", ink="#282215", muted="#6b6250", rule="#b9ad92", blue="#3b42db", hot="#e85b30", part="#f6f1e4", gold="#a9822a"),
    "dark": dict(paper="#1c1c1c", board="#262626", ink="#f1ede4", muted="#a39b8a", rule="#4a4a4a", blue="#6f76ec", hot="#d95526", part="#2f2f2f", gold="#c9a24a"),
}
P, X0, Y0, SECH = 44, 100, 140, 540
ROW = {"U": 0, "T": 1, "A": 2.4, "B": 3.4, "C": 4.4, "D": 5.4, "E": 6.4, "V": 7.8, "W": 8.8}
TITLE = {1: "S1 · top · boost converter and relay 1", 2: "S2 · middle · XIAO and current sink", 3: "S3 · bottom · LM358 and relay 2"}
W, H = 1280, Y0 + 3 * SECH + 40


def xy(h):
    s, c, r = h
    return X0 + (c - 1) * P, Y0 + (s - 1) * SECH + ROW[r] * P


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(t: dict) -> str:
    o: list[str] = []
    a = o.append

    def text(x, y, s, size=12, fill=None, anchor="start", weight=400):
        a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill or t["ink"]}" text-anchor="{anchor}">{esc(s)}</text>')

    def line(pts, c, w=1.6, dash=False, cap="round"):
        d = ' stroke-dasharray="5 4"' if dash else ""
        a(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="{cap}" stroke-linejoin="round"{d}/>')

    a(f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>')
    text(32, 40, "The perfboard, front", 22, weight=500)
    text(32, 64, "Parts side. HV bus on column 4, ground on column 6, XIAO USB-C pointing right. Dashed lines are bare-wire bridges on the back.", 13, t["muted"])

    used = set()
    for _, _, legs, _ in L.parts:
        used |= {h for h, _ in legs}
    for h, _ in L.ext:
        used.add(h)
    for a1, b1, _ in L.jumpers:
        used |= {a1, b1}

    for sec in (1, 2, 3):
        x1, y1 = xy((sec, 1, "U")); x2, y2 = xy((sec, 20, "W"))
        a(f'<rect x="{x1-34}" y="{y1-34}" width="{x2-x1+68}" height="{y2-y1+68}" rx="10" fill="{t["board"]}" stroke="{t["rule"]}" stroke-width="1.5"/>')
        text(x1 - 34, y1 - 46, TITLE[sec], 13, t["muted"], weight=500)
        # header pairs
        for cols, (r1, r2) in ((L.TOPCOLS, ("U", "T")), (L.BOTCOLS, ("V", "W"))):
            for c in cols:
                (x, ya), (_, yb) = xy((sec, c, r1)), xy((sec, c, r2))
                a(f'<rect x="{x-12}" y="{ya-12}" width="24" height="{yb-ya+24}" rx="12" fill="none" stroke="{t["gold"]}" stroke-width="1.3" opacity="0.8"/>')
        for c in range(1, 21):
            rows = "ABCDETUVW" if c in (4, 6) else "ABCDE"
            for r in rows:
                x, y = xy((sec, c, r))
                col = t["hot"] if c == 4 else t["blue"] if c == 6 else t["rule"]
                a(f'<circle cx="{x}" cy="{y}" r="6.5" fill="none" stroke="{col}" stroke-width="{2 if c in (4, 6) else 1.3}"/>')
            x, _ = xy((sec, c, "A"))
            col = t["hot"] if c == 4 else t["blue"] if c == 6 else t["muted"]
            text(x, y1 - 14, str(c), 12, col, "middle", 500 if c in (4, 6) else 400)
        for r in "ABCDE":
            _, y = xy((sec, 1, r)); text(x1 - 48, y + 4, r, 13, t["muted"], "end")
        for r, lab in (("U", "U"), ("T", "T"), ("V", "V"), ("W", "W")):
            _, y = xy((sec, 1, r)); text(x1 - 48, y + 4, lab, 11, t["gold"], "end")
        text(xy((sec, 4, "W"))[0], y2 + 28, "HV", 11, t["hot"], "middle", 500)
        text(xy((sec, 6, "W"))[0], y2 + 28, "GND", 11, t["blue"], "middle", 500)

    # bare-wire bridges (on the back)
    for path in L.bridges:
        if len(path) > 1:
            line([xy(h) for h in path], t["muted"], 1.6, dash=True)
    for h in used:
        x, y = xy(h); a(f'<circle cx="{x}" cy="{y}" r="4.2" fill="{t["gold"]}"/>')

    def pill(p1, p2, label, polarity=None, kind=""):
        (x1, y1), (x2, y2) = p1, p2
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d = math.hypot(x2 - x1, y2 - y1)
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if ang > 90 or ang < -90:
            ang += 180
        w = max(34, min(d - 10, 76)); h = 20
        line([(x1, y1), (x2, y2)], t["muted"], 1.5)
        a(f'<g transform="translate({mx:.1f} {my:.1f}) rotate({ang:.1f})"><rect x="{-w/2}" y="-10" width="{w}" height="{h}" rx="9" fill="{t["part"]}" stroke="{t["ink"]}" stroke-width="1.3"/>')
        a(f'<text x="0" y="4" font-size="11" fill="{t["ink"]}" text-anchor="middle" font-weight="500" transform="rotate({-ang:.1f})">{esc(label)}</text></g>')
        return mx, my

    for name, lab, legs, kind in L.parts:
        pts = [xy(h) for h, _ in legs]
        if kind in ("rflat", "rstand", "film", "ind", "diode", "ecap"):
            pill(pts[0], pts[1], lab)
            if kind == "ecap":
                px, py = pts[0]; text(px + 9, py - 8, "+", 14, t["hot"], "middle", 500)
            if kind == "diode":  # legs are K then A: mark the cathode end
                kx, ky = pts[0]; text(kx - 12, ky - 9, "K", 10, t["hot"], "middle", 500)
        elif kind == "npnv":
            (xe, ye), (xb, yb), (xc, yc) = pts
            a(f'<rect x="{xe-17}" y="{min(ye, yc)-14}" width="34" height="{abs(yc-ye)+28}" rx="14" fill="{t["part"]}" stroke="{t["ink"]}" stroke-width="1.3"/>')
            for (x, y), pin in zip(pts, "EBC"):
                text(x - 24, y + 4, pin, 11, t["hot"], "end", 500)
            text(xe + 26, (ye + yc) / 2 + 4, f"{name} {lab}", 11, t["ink"], "start", 500)
        elif kind == "dip":
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            x1, x2, y1, y2 = min(xs) - 20, max(xs) + 20, min(ys) - 16, max(ys) + 16
            a(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="5" fill="{t["part"]}" stroke="{t["ink"]}" stroke-width="1.3"/>')
            a(f'<path d="M{(x1+x2)/2-9} {y2} a9 9 0 0 1 18 0" fill="{t["ink"]}" opacity="0.5"/>')
            text((x1 + x2) / 2, (y1 + y2) / 2 + 4, "LM358", 12, t["ink"], "middle", 500)
            for (x, y), (h, pin) in zip(pts, legs):
                left = x == min(xs); text(x + (-24 if left else 24), y + 4, pin, 11, t["hot"], "end" if left else "start", 500)
        elif kind == "xiao":
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            x1, x2, y1, y2 = min(xs) - 24, max(xs) + 24, min(ys) - 20, max(ys) + 20
            a(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="8" fill="{t["part"]}" stroke="{t["ink"]}" stroke-width="1.6" opacity="0.95"/>')
            a(f'<rect x="{x2-2}" y="{(y1+y2)/2-18}" width="28" height="36" rx="4" fill="none" stroke="{t["ink"]}" stroke-width="1.3"/>')
            text(x2 + 32, (y1 + y2) / 2 + 4, "USB-C", 11, t["muted"])
            text((x1 + x2) / 2, (y1 + y2) / 2 - 2, "XIAO ESP32-C3", 14, t["ink"], "middle", 500)
            text((x1 + x2) / 2, (y1 + y2) / 2 + 16, "chip side up", 11, t["muted"], "middle")
            for (x, y), (h, pin) in zip(pts, legs):
                text(x, y + (22 if h[2] == "T" else -12), pin, 11, t["blue"], "middle", 500)
        elif kind == "relay":
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            bx = max(xs) + 64; by1, by2 = min(ys) - 26, max(ys) + 26
            a(f'<rect x="{bx}" y="{by1}" width="190" height="{by2-by1}" rx="6" fill="{t["part"]}" stroke="{t["ink"]}" stroke-width="1.6"/>')
            text(bx + 50, by1 + 26, lab, 14, t["ink"], weight=500)
            text(bx + 50, by1 + 46, "5 V coil module,", 11, t["muted"]); text(bx + 50, by1 + 62, "NO · COM · NC on", 11, t["muted"]); text(bx + 50, by1 + 78, "its screw terminals", 11, t["muted"])
            for (x, y), (h, pin) in zip(pts, legs):
                line([(x, y), (bx + 8, y)], t["blue"] if pin == "S" else t["hot"] if pin == "+" else t["muted"], 1.8)
                text(bx + 16, y + 4, pin if pin != "-" else "−", 13, t["ink"], weight=500)

    # off-board connections that land on the board
    for h, lab in L.ext:
        x, y = xy(h)
        if lab.startswith("battery"):
            text(x - 6, y - 24, "BAT+ wire from the XIAO", 11, t["hot"], "end", 500)
        else:
            left = h[1] <= 2
            text(x, y - 11 if left else y + 26, lab.replace("Relay ", "R"), 10.5, t["hot"], "middle", 500)

    # jumpers
    def jcolor(label: str) -> str:
        return t["hot"] if ("HV" in label or "BAT" in label) else t["muted"] if "GND" in label else t["blue"]

    for i, (a1, b1, label) in enumerate(L.jumpers):
        tag = f"J{i+1}"
        col = jcolor(label)
        (x1, y1), (x2, y2) = xy(a1), xy(b1)
        if a1[0] == b1[0]:
            cy = min(y1, y2) - 34 if max(y1, y2) < xy((a1[0], 1, "E"))[1] + 1 else max(y1, y2) + 34
            cx = (x1 + x2) / 2
            a(f'<path d="M{x1} {y1} Q{cx} {cy} {x2} {y2}" fill="none" stroke="{col}" stroke-width="3" stroke-linecap="round"/>')
            tx, ty = (x1 + 2 * cx + x2) / 4, (y1 + 2 * cy + y2) / 4
            a(f'<rect x="{tx-17}" y="{ty-10}" width="34" height="18" rx="4" fill="{col}"/>'); text(tx, ty + 3, tag, 11, t["paper"], "middle", 500)
        else:
            for (x, y), other in (((x1, y1), b1), ((x2, y2), a1)):
                down = y > xy((1, 1, "A"))[1] and False
                ex, ey = x + 20, y - 24
                line([(x, y), (ex, ey)], col, 3)
                a(f'<rect x="{ex-2}" y="{ey-16}" width="{10 + 7 * (len(tag) + len(label) + 4)}" height="18" rx="4" fill="{col}"/>')
                text(ex + 3, ey - 3, f"{tag} {label}", 11, t["paper"], "start", 500)

    ly = H - 70
    text(32, ly, "Red column 4 is the HV bus and blue column 6 is ground, on all three sections. The header rows U and T (top) and V and W (bottom) are joined per column.", 12, t["muted"])
    text(32, ly + 18, "Gold dot: a leg or wire lands here. Dashed: bare-wire bridge on the back. Coloured jumpers: red for HV and battery, grey for ground, blue for signals.", 12, t["muted"])
    text(32, ly + 36, "A jumper that goes to another section is drawn as two tags, one at each end. J1 to J13 are listed in docs/HARDWARE.md.", 12, t["muted"])
    body = "\n".join(o)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}" role="img" aria-labelledby="t">'
            f'<title id="t">Front of the perfboard: boost converter, XIAO ESP32-C3 and current sink, LM358 and relays, with every jumper tagged J1 to J13</title>\n{body}\n</svg>\n')


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    (out / "perfboard.svg").write_text(render(THEMES["light"]))
    (out / "perfboard-dark.svg").write_text(render(THEMES["dark"]))
    print(f"wrote perfboard.svg and perfboard-dark.svg in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
