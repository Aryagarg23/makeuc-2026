"""Circuit schematic and pinout figure for the GVS board, drawn from the as-built netlist.

  python3 docs/figures/schematic.py docs/figures        writes schematic.svg and pinout.svg

Nets come from gvs/board/layout.py (what was soldered) and gvs/HANDOFF.md, and agree with the SPICE model
in gvs/board/sim.py, which is built from the same layout. Colours: ink = circuit, red-orange = the high
voltage and current path (the part that goes through a head), blue = signals to and from the XIAO.
"""
from __future__ import annotations

import sys
from pathlib import Path

PAPER, INK, MUTED, RULE, BLUE, HOT = "#eae4d6", "#282215", "#6b6250", "#c6b99f", "#3b42db", "#e85b30"
FONT = "Space Grotesk, Inter, system-ui, sans-serif"


class S:
    def __init__(self, w, h):
        self.w, self.h, self.o = w, h, []

    def wire(self, pts, c=INK, w=1.5, dash=False):
        d = ' stroke-dasharray="5 4"' if dash else ""
        self.o.append(f'<polyline points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="none" stroke="{c}" stroke-width="{w}"{d}/>')

    def dot(self, x, y, c=INK):
        self.o.append(f'<circle cx="{x}" cy="{y}" r="3.2" fill="{c}"/>')

    def text(self, x, y, s, size=12, fill=INK, anchor="start", weight=400):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>')

    def label(self, x, y, s, fill=MUTED):
        self.text(x, y, s.upper(), 10.5, fill)
        self.o[-1] = self.o[-1].replace("<text ", '<text letter-spacing="1.4" ')

    # ---- parts: each returns its two or three pin coordinates ----
    def res_h(self, cx, cy, lab, c=INK, above=True):
        self.o.append(f'<rect x="{cx-24}" y="{cy-7}" width="48" height="14" fill="{PAPER}" stroke="{c}" stroke-width="1.5"/>')
        self.text(cx, cy - 12 if above else cy + 22, lab, 11.5, MUTED, "middle")
        return (cx - 24, cy), (cx + 24, cy)

    def res_v(self, cx, cy, lab, c=INK, side=1):
        self.o.append(f'<rect x="{cx-7}" y="{cy-24}" width="14" height="48" fill="{PAPER}" stroke="{c}" stroke-width="1.5"/>')
        self.text(cx + 14 * side, cy + 4, lab, 11.5, MUTED, "start" if side > 0 else "end")
        return (cx, cy - 24), (cx, cy + 24)

    def cap_v(self, cx, cy, lab, polar=False, side=1):
        self.wire([(cx - 11, cy - 4), (cx + 11, cy - 4)]); self.wire([(cx - 11, cy + 4), (cx + 11, cy + 4)])
        self.text(cx + 16 * side, cy + 4, lab + (" +" if polar else ""), 11.5, MUTED, "start" if side > 0 else "end")
        return (cx, cy - 4), (cx, cy + 4)

    def cap_h(self, cx, cy, lab):
        self.wire([(cx - 4, cy - 11), (cx - 4, cy + 11)]); self.wire([(cx + 4, cy - 11), (cx + 4, cy + 11)])
        self.text(cx, cy - 16, lab, 11.5, MUTED, "middle")
        return (cx - 4, cy), (cx + 4, cy)

    def diode_h(self, cx, cy, lab, c=INK):
        self.o.append(f'<polygon points="{cx-10},{cy-9} {cx-10},{cy+9} {cx+10},{cy}" fill="{PAPER}" stroke="{c}" stroke-width="1.5"/>')
        self.wire([(cx + 10, cy - 9), (cx + 10, cy + 9)], c)
        self.text(cx, cy - 16, lab, 11.5, MUTED, "middle")
        return (cx - 10, cy), (cx + 10, cy)

    def ind_v(self, cx, cy, lab):
        d = f"M{cx},{cy-28} " + " ".join(f"a7,7 0 0 1 0,14" for _ in range(4))
        self.o.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
        self.text(cx + 14, cy + 4, lab, 11.5, MUTED)
        return (cx, cy - 28), (cx, cy + 28)

    def npn(self, cx, cy, lab):
        self.o.append(f'<circle cx="{cx}" cy="{cy}" r="22" fill="none" stroke="{INK}" stroke-width="1.2"/>')
        self.wire([(cx - 8, cy - 14), (cx - 8, cy + 14)], INK, 2)
        self.wire([(cx - 30, cy), (cx - 8, cy)])
        self.wire([(cx - 8, cy - 6), (cx + 10, cy - 18), (cx + 10, cy - 30)])
        self.wire([(cx - 8, cy + 6), (cx + 10, cy + 18), (cx + 10, cy + 30)])
        self.o.append(f'<polygon points="{cx+10},{cy+18} {cx+2},{cy+17} {cx+7},{cy+10}" fill="{INK}"/>')
        self.text(cx - 18, cy - 28, lab, 11.5, MUTED, "end")
        return (cx - 30, cy), (cx + 10, cy - 30), (cx + 10, cy + 30)  # base, collector, emitter

    def opamp(self, x, y, lab):
        self.o.append(f'<polygon points="{x},{y-40} {x},{y+40} {x+80},{y}" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>')
        self.text(x + 6, y - 15, "+", 14); self.text(x + 6, y + 25, "−", 14)
        self.text(x + 30, y + 4, lab, 11.5, MUTED)
        return (x, y - 20), (x, y + 20), (x + 80, y), (x + 30, y - 25)  # +, -, out, vcc

    def box(self, x, y, w, h, lines, c=INK, tc=INK):
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PAPER}" stroke="{c}" stroke-width="1.5"/>')
        for i, ln in enumerate(lines):
            self.text(x + 10, y + 20 + 16 * i, ln, 13 if i == 0 else 11.5, tc if i == 0 else MUTED, weight=500 if i == 0 else 400)

    def write(self, path, title):
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                        f'font-family="{FONT}" role="img" aria-labelledby="t"><title id="t">{title}</title>'
                        f'<rect width="{self.w}" height="{self.h}" fill="{PAPER}"/>\n' + "\n".join(self.o) + "\n</svg>\n")


def relay(s: "S", x: int, y: int, name: str, pin: str) -> None:
    s.o.append(f'<rect x="{x}" y="{y}" width="150" height="80" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>')
    s.text(x + 30, y + 22, name, 13, INK, weight=500)
    s.text(x + 30, y + 42, f"coil S ← {pin}", 11.5, MUTED)
    s.text(x + 30, y + 58, "coil + BAT, − GND", 11.5, MUTED)
    s.text(x + 6, y + 24, "NO", 11, MUTED); s.text(x + 6, y + 64, "NC", 11, MUTED)


def schematic(out: Path) -> None:
    s = S(1400, 860)
    GND, HVY, BATY = 800, 240, 90
    s.label(16, 24, "GVS board · schematic as built · 3.7 V LiPo only · see docs/HARDWARE.md for the parts and the perfboard holes")
    # rails
    s.wire([(60, GND), (1160, GND)], INK, 2); s.text(1170, GND + 4, "GND", 12, MUTED)
    s.wire([(72, BATY), (1020, BATY)], INK, 2); s.text(1030, BATY - 6, "BAT+ (3.7 to 4.2 V)", 12, MUTED)
    s.wire([(300, HVY), (880, HVY)], HOT, 2.5); s.text(310, HVY - 8, "HV bus (boost, 17 to 24 V under load, cut off at 28 V)", 12, HOT)
    # battery
    s.box(40, 130, 64, 70, ["LiPo", "250 mAh"])
    s.wire([(72, BATY), (72, 130)]); s.wire([(72, 200), (72, GND)])
    # --- boost converter ---
    s.label(130, 64, "Boost converter, runs only during a pulse", HOT)
    lt, lb = s.ind_v(170, 170, "1 mH")
    s.wire([(170, BATY), lt]); s.dot(170, BATY)
    s.wire([lb, (170, HVY)])
    s.dot(170, HVY); s.o.append("")
    s.wire([(170, HVY), (211, HVY)]); da, dk = s.diode_h(225, HVY, "1N5819", HOT); s.wire([dk, (300, HVY)], HOT); s.dot(300, HVY, HOT)
    b, c, e = s.npn(160, 330, "Q1 2N3904")
    s.wire([(170, HVY), c]); s.wire([e, (170, GND)])
    s.text(16, 334, "D10", 12, BLUE, weight=500); s.wire([(46, 330), (47, 330)], BLUE)
    r1a, r1b = s.res_h(95, 330, "330 Ω"); s.wire([(40, 330), r1a], BLUE); s.wire([r1b, b])
    s.dot(125, 330)
    ra, rb = s.res_v(125, 410, "10k", side=-1); s.wire([(125, 330), ra]); s.wire([rb, (125, GND)])
    s.wire([(125, 436), (125, 436)])
    ca, cb = s.cap_v(320, 330, "47 µF", True, side=-1); s.wire([(320, HVY), ca], HOT); s.wire([cb, (320, GND)])
    s.dot(320, HVY, HOT)
    ra, rb = s.res_v(380, 350, "10k bleed"); s.wire([(380, HVY), ra], HOT); s.wire([rb, (380, GND)]); s.dot(380, HVY, HOT)
    ra, rb = s.res_v(440, 310, "100k"); s.wire([(440, HVY), ra], HOT); s.dot(440, HVY, HOT)
    s.wire([rb, (440, 380)]); s.dot(440, 380)
    ra2, rb2 = s.res_v(440, 430, "8.2k"); s.wire([(440, 380), ra2]); s.wire([rb2, (440, GND)])
    s.wire([(440, 380), (500, 380)], BLUE); s.text(506, 384, "D2  HV sense (÷ 13.2)", 12, BLUE, weight=500)
    # --- current sink ---
    s.label(560, 64, "Current sink: I = V_SET / 1100 Ω", HOT)
    cap_a, cap_b = s.cap_v(650, 330, "104"); s.wire([(650, HVY), cap_a], HOT); s.wire([cap_b, (650, GND)]); s.dot(650, HVY, HOT)
    inp, inm, outp, vcc = s.opamp(740, 420, "LM358")
    s.wire([(770, HVY), vcc], HOT); s.dot(770, HVY, HOT)
    # SET network
    s.text(520, 404, "D3  SET PWM", 12, BLUE, weight=500); s.text(520, 420, "20 kHz, 10-bit", 11, MUTED)
    s.wire([(594, 400), (626 - 0, 400)], BLUE)
    ra, rb = s.res_h(650, 400, "10k"); s.wire([(594, 400), ra], BLUE); s.wire([rb, (700, 400)], BLUE); s.dot(700, 400)
    s.wire([(700, 400), inp])
    s.dot(600, 400, BLUE)
    ra, rb = s.res_v(600, 470, "100k", side=-1); s.wire([(600, 400), ra]); s.wire([rb, (600, GND)])
    ca, cb = s.cap_v(700, 470, "1 µF", True); s.wire([(700, 400), ca]); s.wire([cb, (700, GND)])
    # feedback + base drive
    s.dot(835, 420)
    r1a, r1b = s.res_h(870, 420, "1k"); s.wire([outp, r1a]); s.wire([r1b, (910, 420), (910, 520)])
    s.wire([(835, 420), (835, 360)]); ca, cb = s.cap_h(775, 360, "10 nF"); s.wire([(835, 360), cb]); s.wire([ca, (715, 360), (715, 440), inm]); s.dot(715, 440)
    fa, fb = s.res_h(666, 440, "1k", above=False); s.wire([fb, (715, 440)])
    b2, c2, e2 = s.npn(960, 520, "Q2 2N3904")
    s.wire([(910, 520), b2])
    s.text(980, 470, "BOTTOM", 12, HOT, weight=500)
    # SENSE node and its parts
    s.wire([e2, (970, 600)], HOT); s.dot(970, 600, HOT)
    s.text(975, 592, "SENSE", 12, MUTED)
    s.wire([fa, (642, 440), (642, 600), (970, 600)])
    ra, rb = s.res_v(970, 660, "1k", side=1); s.wire([(970, 600), ra], HOT); s.wire([rb, (970, 706)], HOT)
    ra, rb = s.res_v(970, 730, "100 Ω", side=1); s.wire([(970, 706), ra], HOT); s.wire([rb, (970, GND)], HOT)
    s.wire([(970, 600), (1040, 600)]); ra, rb = s.res_h(1075, 600, "100k"); s.wire([(1040, 600), ra]); s.wire([rb, (1110, 600)]); s.dot(1110, 600)
    s.wire([(1110, 600), (1190, 600)], BLUE); s.text(1196, 604, "D1  current readback (÷ 2)", 12, BLUE, weight=500)
    ra, rb = s.res_v(1110, 670, "100k", side=1); s.wire([(1110, 600), ra]); s.wire([rb, (1110, GND)])
    # --- relays + head ---
    s.label(1030, 214, "Polarity: two SPDT relays", HOT)
    ra, rb = s.res_v(880, 300, "2.2 kΩ (TOP)", side=1); s.wire([(880, HVY), ra], HOT); s.wire([rb, (880, 350), (1015, 350)], HOT); s.dot(880, 350, HOT)
    s.wire([(1015, 320), (1015, 440)], HOT)
    s.wire([(970, 490), (970, 430), (1000, 430)], HOT); s.dot(970, 430, HOT)
    s.wire([(1000, 360), (1000, 480)], HOT)
    relay(s, 1030, 300, "Relay 1", "D4")
    relay(s, 1030, 420, "Relay 2", "D5")
    s.wire([(1015, 320), (1030, 320)], HOT); s.wire([(1000, 360), (1030, 360)], HOT)
    s.wire([(1015, 440), (1030, 440)], HOT); s.wire([(1000, 480), (1030, 480)], HOT)
    s.text(1198, 334, "COM", 11, MUTED, "middle"); s.text(1198, 454, "COM", 11, MUTED, "middle")
    s.wire([(1180, 340), (1215, 340)], HOT); s.o.append(f'<rect x="1215" y="325" width="64" height="30" fill="{PAPER}" stroke="{HOT}" stroke-width="1.5"/>')
    s.text(1247, 344, "KILL SW", 11.5, HOT, "middle"); s.wire([(1279, 340), (1328, 340)], HOT)
    s.o.append(f'<circle cx="1340" cy="340" r="12" fill="{PAPER}" stroke="{HOT}" stroke-width="2"/>'); s.text(1340, 372, "left mastoid", 12, HOT, "middle")
    s.wire([(1180, 460), (1328, 460)], HOT)
    s.o.append(f'<circle cx="1340" cy="460" r="12" fill="{PAPER}" stroke="{HOT}" stroke-width="2"/>'); s.text(1340, 492, "right mastoid", 12, HOT, "middle")
    s.text(1020, 520, "A relay is energized one at a time.", 11.5, MUTED); s.text(1020, 536, "Relay 1 on: left → TOP, right → BOTTOM.", 11.5, MUTED)
    s.text(1020, 552, "Relay 2 on: right → TOP, left → BOTTOM.", 11.5, MUTED); s.text(1020, 568, "Both off: both electrodes on BOTTOM, no path.", 11.5, MUTED)
    # reading notes
    s.box(40, 560, 380, 108, ["How to read it", "The firmware sets V_SET with D3. The LM358 drives Q2 until the", "voltage on SENSE equals V_SET, so I = V_SET / 1.1 kΩ whatever", "the head does, until HV runs out. HV − (TOP drop) − (SENSE", "drop) − 0.2 V is all the head can have."])
    s.write(out / "schematic.svg", "Schematic of the GVS board: boost converter, LM358 and 2N3904 current sink, two relays, kill switch and electrodes")


def pinout(out: Path) -> None:
    s = S(960, 640)
    s.label(16, 24, "XIAO ESP32-C3 · what each pin does on this board")
    s.o.append(f'<rect x="380" y="60" width="200" height="500" fill="{PAPER}" stroke="{INK}" stroke-width="2"/>')
    s.text(480, 90, "XIAO ESP32-C3", 14, INK, "middle", 500); s.text(480, 108, "chip side up, USB-C at the top", 11.5, MUTED, "middle")
    s.o.append(f'<rect x="450" y="56" width="60" height="22" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>'); s.text(480, 72, "USB-C", 11, MUTED, "middle")
    left = [("D0", "GPIO2", "not used. Boot-strapping pin: leave it alone.", MUTED), ("D1", "GPIO3 · ADC1", "current readback: SENSE ÷ 2 (100k / 100k)", BLUE),
            ("D2", "GPIO4 · ADC1", "HV sense: HV ÷ 13.2 (100k / 8.2k)", BLUE), ("D3", "GPIO5", "SET: 20 kHz, 10-bit PWM, then 10k + 1 µF", BLUE),
            ("D4", "GPIO6", "relay 1 coil (left electrode on TOP)", BLUE), ("D5", "GPIO7", "relay 2 coil (right electrode on TOP)", BLUE),
            ("D6", "GPIO21 · TX", "not used", MUTED)]
    right = [("5V", "", "not used (USB 5 V only)", MUTED), ("GND", "", "circuit ground, relay − pins", INK), ("3V3", "", "not used", MUTED),
             ("D10", "GPIO10", "boost PWM → 330 Ω → Q1 base", BLUE), ("D9", "GPIO9", "not used", MUTED), ("D8", "GPIO8", "not used", MUTED), ("D7", "GPIO20 · RX", "not used", MUTED)]
    for i, (n, g, f, c) in enumerate(left):
        y = 140 + i * 56
        s.wire([(330, y), (380, y)], c, 2); s.text(372, y - 6, n, 13, c, "end", 500)
        s.text(320, y - 6, f, 12, c, "end"); s.text(320, y + 10, g, 11, MUTED, "end")
    for i, (n, g, f, c) in enumerate(right):
        y = 140 + i * 56
        s.wire([(580, y), (630, y)], c, 2); s.text(588, y - 6, n, 13, c, "start", 500)
        s.text(640, y - 6, f, 12, c); s.text(640, y + 10, g, 11, MUTED)
    s.o.append(f'<rect x="395" y="500" width="170" height="40" fill="{PAPER}" stroke="{HOT}" stroke-width="1.5"/>')
    s.text(480, 517, "BAT+ / BAT− pads (underside)", 11.5, HOT, "middle", 500); s.text(480, 532, "3.7 V LiPo, soldered permanently", 11, MUTED, "middle")
    s.text(16, 610, "BAT+ also goes to S1 col 19 by one black wire (J12) and feeds the relay + pins and the boost inductor.", 11.5, MUTED)
    s.text(16, 628, "D1 and D2 are on ADC1 on purpose: D3 (GPIO5) is on ADC2, which cannot be read while WiFi is on.", 11.5, MUTED)
    s.write(out / "pinout.svg", "XIAO ESP32-C3 pinout as used on the GVS board")


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    schematic(out); pinout(out)
    print(f"wrote {out}/schematic.svg {out}/pinout.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
