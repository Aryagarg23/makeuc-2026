"""The two figures for the HVAC writeup on aryagarg23.com: the wiring diagram and the software map.

  python3 docs/figures/site_figures.py OUT_DIR      writes wiring.svg and software.svg

Print register of the site's design system: cream ground, ink hairlines, blue for signal paths, hot
for the current path and the warning. Facts come from gvs/HANDOFF.md, gvs/README.md, pipeline/README.md
and uno_q/fun/fun_server.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

PAPER, INK, MUTED, RULE, BLUE, HOT = "#eae4d6", "#282215", "#6b6250", "#c6b99f", "#3b42db", "#e85b30"
FONT = "Space Grotesk, Inter, system-ui, sans-serif"


class Svg:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h, self.parts = w, h, []

    def box(self, x, y, w, h, lines, stroke=INK, title_fill=INK, dash=False, sw=1):
        d = ' stroke-dasharray="4 4"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PAPER}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
        ty = y + 22
        for i, line in enumerate(lines):
            size, fill, weight = (14, title_fill, 500) if i == 0 else (12, MUTED, 400)
            self.parts.append(f'<text x="{x + 12}" y="{ty}" font-size="{size}" font-weight="{weight}" fill="{fill}">{esc(line)}</text>')
            ty += 18 if i == 0 else 16
        return x, y, w, h

    def text(self, x, y, s, size=12, fill=MUTED, anchor="start", weight=400):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')

    def label(self, x, y, s, fill=MUTED):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="10.5" letter-spacing="1.4" fill="{fill}">{esc(s.upper())}</text>')

    def arrow(self, pts, color=INK, label=None, lx=None, ly=None, dash=False):
        d = ' stroke-dasharray="4 4"' if dash else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        m = {INK: "ink", BLUE: "blue", HOT: "hot"}[color]
        self.parts.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="1.2" marker-end="url(#a-{m})"{d}/>')
        if label:
            x, y = (lx, ly) if lx is not None else ((pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2 - 6)
            self.parts.append(f'<text x="{x}" y="{y}" font-size="11" fill="{color}" text-anchor="middle">{esc(label)}</text>')

    def line(self, pts, color=INK, dash=False, sw=1.2):
        d = ' stroke-dasharray="4 4"' if dash else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.parts.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"{d}/>')

    def write(self, path: Path, title: str) -> None:
        defs = "".join(
            f'<marker id="a-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
            f'<path d="M1 1L9 5L1 9" fill="none" stroke="{c}" stroke-width="1.4"/></marker>'
            for n, c in (("ink", INK), ("blue", BLUE), ("hot", HOT)))
        body = "\n".join(self.parts)
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
            f'font-family="{FONT}" role="img" aria-labelledby="t">\n<title id="t">{esc(title)}</title>\n<defs>{defs}</defs>\n'
            f'<rect width="{self.w}" height="{self.h}" fill="{PAPER}"/>\n{body}\n</svg>\n')


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wiring(out: Path) -> None:
    s = Svg(1000, 640)
    s.label(40, 30, "HVAC · wiring, as built (XIAO ESP32-C3 on a FeatherWing Tripler perfboard)")
    # power
    s.box(40, 60, 160, 64, ["3.7 V LiPo, 250 mAh", "soldered to the BAT pads", "the only supply"])
    s.box(250, 50, 180, 250, ["XIAO ESP32-C3", "firmware: HTTP + BLE,", "limits enforced on-board"])
    s.arrow([(200, 92), (250, 92)], label="BAT", lx=225, ly=84)
    pins = [("D10", "boost PWM", 150), ("D2", "HV sense", 180), ("D3", "SET PWM, 20 kHz, 10-bit", 210), ("D1", "current readback", 240), ("D4 / D5", "relay coils", 270)]
    for name, what, y in pins:
        s.text(262, y, name, 12, INK, weight=500)
        s.text(318, y, what, 11.5)
    # boost + HV
    s.box(500, 50, 220, 80, ["Boost converter", "Q1 2N3904 · 1 mH · 1N5819 · 47 µF", "HV 20–24 V · firmware cutoff 28 V"], stroke=HOT, title_fill=HOT)
    s.arrow([(430, 146), (465, 146), (465, 90), (500, 90)], BLUE, "330 Ω", 482, 82)
    s.box(500, 150, 220, 52, ["HV sense  100k / 8.2k → D2", "10k bleed, HV bus → GND"])
    s.arrow([(500, 176), (465, 176), (465, 176), (430, 176)], BLUE)
    s.line([(720, 90), (760, 90), (760, 330)], HOT)
    s.text(772, 210, "HV bus", 11, HOT)
    # sink
    s.box(500, 230, 220, 92, ["Current sink", "LM358 → Q2 2N3904", "1.1 kΩ emitter: I = V_SET / 1100", "readback 100k / 100k → D1"])
    s.arrow([(430, 206), (465, 206), (465, 262), (500, 262)], BLUE, "10k + 1 µF", 482, 256)
    s.arrow([(500, 300), (465, 300), (465, 236), (430, 236)], BLUE)
    # relays
    s.box(760, 330, 220, 110, ["Relays, 5 V modules, D4 / D5", "NO → TOP: HV through 2.2 kΩ", "NC → BOTTOM: the sink", "COM → an electrode each", "one energized at a time: polarity"])
    s.arrow([(430, 266), (470, 266), (470, 352), (760, 352)], BLUE, "D4 / D5", 620, 344)
    s.arrow([(720, 290), (740, 290), (740, 380), (760, 380)], HOT, "BOTTOM", 720, 400)
    s.arrow([(760, 330), (760, 330)], HOT)
    s.text(772, 320, "TOP ← HV via 2.2 kΩ (compliance limit)", 11, HOT)
    # electrodes
    s.box(760, 480, 100, 44, ["Kill switch", "in hand"], stroke=HOT, title_fill=HOT)
    s.box(880, 480, 100, 44, ["Left", "mastoid"], stroke=HOT, title_fill=HOT)
    s.box(880, 560, 100, 44, ["Right", "mastoid"], stroke=HOT, title_fill=HOT)
    s.arrow([(780, 440), (780, 480)], HOT, "relay 1 COM", 810, 466)
    s.arrow([(860, 502), (880, 502)], HOT)
    s.arrow([(940, 440), (940, 560)], HOT, "relay 2 COM", 905, 540)
    s.text(880, 626, "~1 mA sine burst, 1 Hz, whole cycles", 11, HOT)
    # warning + limits
    s.box(40, 340, 430, 128, ["Danger. Current through the head can cause permanent harm.",
                               "Battery only. Never with the laptop on its charger.",
                               "Seated, kill switch in hand, a second person present.",
                               "Dummy loads (2.2k, 4.7k) before any skin. Start 0.5 mA, max 2.0 mA.",
                               "Not for epilepsy, implants or balance disorders.",
                               "Stop on flashes of light, burning, nausea or headache."], stroke=HOT, title_fill=HOT, sw=1.5)
    s.box(40, 490, 430, 114, ["Limits the board enforces itself",
                               "2.0 mA · 3000 ms · 5 s cooldown · 30 pulses per hour",
                               "HV cutoff 28 V (3 readings) · current readback trip",
                               "PWM must attach or the board faults at boot",
                               "token on every command · dead-man 1 s in live mode"])
    s.write(out / "wiring.svg", "HVAC wiring diagram: battery, XIAO ESP32-C3, boost converter, current sink, two relays, kill switch, two electrodes")


def software(out: Path) -> None:
    s = Svg(1000, 640)
    s.label(40, 30, "HVAC · software map")
    s.box(40, 50, 150, 70, ["Your devices", "phone, laptop, …", "one Tailscale network"])
    s.box(240, 50, 240, 70, ["Exit node", "UNO Q as a Tailscale exit node (plan),", "the Mac's tshark over USB (demo)"])
    s.arrow([(190, 85), (240, 85)], label="traffic", lx=215, ly=77)
    s.box(530, 50, 170, 70, ["Packet lines", "tshark, one tab-separated", "line per packet"])
    s.arrow([(480, 85), (530, 85)])
    # pipeline
    s.box(40, 160, 660, 300, ["gvs_pipeline, pure Python, running on the UNO Q"], dash=True)
    s.arrow([(615, 120), (615, 160)])
    row = [
        (60, 200, 190, 74, ["Names", "DNS answers, TLS SNI, HTTP Host", "→ service per IP"]),
        (270, 200, 190, 74, ["Windows", "3 s long, sliding every 1 s", "under 5 kB/s never counts"]),
        (480, 200, 200, 74, ["Classify", "enrolled domain, or shared domain", "by flow shape, or unnamed by shape"]),
    ]
    for b in row:
        s.box(*b)
    s.arrow([(250, 237), (270, 237)])
    s.arrow([(460, 237), (480, 237)])
    row2 = [
        (60, 310, 190, 74, ["Rules dashboard", "per app: Nauseate, Never, Auto", "weights, pause, key-locked"]),
        (270, 310, 190, 74, ["Trigger", "same bucket 2 windows running,", "then 10 s quiet"]),
        (480, 310, 200, 74, ["Intensity", "weight × max mA (≤ 2.0)", "1 Hz sine, whole cycles"]),
    ]
    for b in row2:
        s.box(*b)
    s.arrow([(580, 274), (580, 292), (155, 292), (155, 310)])
    s.arrow([(250, 347), (270, 347)])
    s.arrow([(460, 347), (480, 347)])
    s.text(60, 430, "Enroll: a 2-minute recording of the thing to punish becomes a bucket (domains + flow shape, weight 0–1).", 11.5)
    s.text(60, 448, "Shared servers (Reels and DMs both use cdninstagram.com) are told apart by flow shape, or not at all.", 11.5)
    # right column
    s.box(760, 160, 220, 70, ["Bluetooth", "GATT, token on every command", "one connection at a time"])
    s.arrow([(680, 347), (720, 347), (720, 195), (760, 195)], BLUE, "pulse ma ms hz pol sine", 715, 150)
    s.box(760, 270, 220, 86, ["XIAO firmware", "caps: 2.0 mA · 3 s · 5 s cooldown", "30 / hour · HV cutoff · readback trip", "refuses what the pipeline gets wrong"])
    s.arrow([(870, 230), (870, 270)], BLUE)
    s.box(760, 400, 220, 60, ["Electrodes", "left and right mastoid"], stroke=HOT, title_fill=HOT)
    s.arrow([(870, 356), (870, 400)], HOT)
    # tribe + fun
    s.box(40, 500, 330, 104, ["TRIBE v2, on the GPU box, at enrollment only", "screen recording → predicted cortical drive", "placed between a neutral and a high anchor", "→ caps the bucket's weight, never raises it"])
    s.arrow([(205, 500), (205, 480), (580, 480), (580, 274)], dash=True)
    s.box(400, 500, 580, 104, ["Fun mode (the same board, a different driver)", "UNO Q hotspot arya-gvs → friends open a page on their phones → tilt slider", "UNO Q sends live mA over Bluetooth at 10 Hz; 0 mA after 1.5 s of silence (dead-man)", "the UNO Q LED matrix shows the tilt; the firmware's caps still apply"])
    s.arrow([(980, 552), (990, 552), (990, 430), (980, 430)], BLUE)
    s.write(out / "software.svg", "HVAC software map: traffic from your devices to packet lines, the pipeline's names, windows, classify, rules, trigger and intensity, Bluetooth to the firmware and electrodes; TRIBE v2 at enrollment; fun mode")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    wiring(out)
    software(out)
    print(f"wrote {out}/wiring.svg {out}/software.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
