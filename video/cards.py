"""Still cards for the pitch video, 1920x1080 PNG. Used by build.py ({"card": {...}}) or on their own:

  .venv/bin/python cards.py software_map assets/software_map.png
  .venv/bin/python cards.py demo out_dir          (one of every card type, for checking)

Card types (dicts, as in an edit list):
  {"type": "title",    "text": "...", "style": "dedsec"|"clean"|"kids"}
  {"type": "headline", "text": "...", "source": "Reuters / AP, Aug 26 2026", "style": ...}
  {"type": "citations","items": ["Authors (year). Title. Venue.", ...], "heading": "How it works"}
  {"type": "results",  "lines": ["Nauseous since 3:30 a.m.", ...], "heading": "Results"}
  {"type": "image",    "path": "../gvs/pictures/full_front.png", "caption": "..."}
  {"type": "software_map"}
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"
TAG, LOGO = "+- II", None  # creator tag / logo, set by build.py from the edit list
STYLES = {  # background, text, accent
    "dedsec": ((8, 8, 12), (235, 240, 245), (255, 40, 140)),
    "clean": ((246, 242, 234), (24, 22, 20), (200, 70, 60)),
    "kids": ((255, 236, 120), (60, 30, 120), (240, 60, 120)),
}


def font(size: int, mono: bool = False, bold: bool = True) -> ImageFont.FreeTypeFont:
    if mono:
        return ImageFont.truetype(MONO, size, index=1 if bold else 0)
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def wrap_draw(d: ImageDraw.ImageDraw, xy, text: str, f, fill, width_chars: int, gap: int = 14) -> int:
    x, y = xy
    for line in textwrap.wrap(text, width_chars):
        d.text((x, y), line, font=f, fill=fill)
        y += f.size + gap
    return y


def base(style: str):
    bg, fg, ac = STYLES[style]
    im = Image.new("RGB", (W, H), bg)
    return im, ImageDraw.Draw(im), fg, ac


def title(c: dict) -> Image.Image:
    style = c.get("style", "dedsec")
    im, d, fg, ac = base(style)
    mono = style == "dedsec"
    f = font(96 if len(c["text"]) < 40 else 72, mono=mono)
    lines = textwrap.wrap(c["text"], 28 if not mono else 30)
    total = len(lines) * (f.size + 20)
    y = (H - total) // 2
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text(((W - tw) / 2, y), line, font=f, fill=fg)
        y += f.size + 20
    if mono:
        d.rectangle([(W - 420) / 2, y + 20, (W + 420) / 2, y + 28], fill=ac)
    return im


def headline(c: dict) -> Image.Image:
    im, d, fg, ac = base(c.get("style", "dedsec"))
    d.rectangle([140, 300, 156, 700], fill=ac)
    y = wrap_draw(d, (200, 300), c["text"], font(78), fg, 34, 18)
    d.text((200, y + 40), c.get("source", ""), font=font(36, bold=False), fill=ac)
    return im


def citations(c: dict) -> Image.Image:
    im, d, fg, ac = base(c.get("style", "clean"))
    d.text((140, 110), c.get("heading", "How it works"), font=font(72), fill=ac)
    y = 260
    for i, item in enumerate(c["items"], 1):
        d.text((140, y), f"[{i}]", font=font(36), fill=ac)
        y = wrap_draw(d, (230, y), item, font(36, bold=False), fg, 78, 10) + 34
    return im


def results(c: dict) -> Image.Image:
    im, d, fg, ac = base(c.get("style", "clean"))
    d.text((140, 120), c.get("heading", "Results"), font=font(72), fill=ac)
    y = 300
    for line in c["lines"]:
        d.ellipse([140, y + 22, 168, y + 50], fill=ac)
        y = wrap_draw(d, (210, y), line, font(64), fg, 40, 12) + 40
    return im


def image(c: dict) -> Image.Image:
    im, d, fg, ac = base(c.get("style", "clean"))
    pic = Image.open(c["path"]).convert("RGB")
    pic.thumbnail((W - 200, H - 220))
    im.paste(pic, ((W - pic.width) // 2, 60))
    if c.get("caption"):
        f = font(44)
        tw = d.textlength(c["caption"], font=f)
        d.text(((W - tw) / 2, H - 110), c["caption"], font=f, fill=fg)
    return im


def software_map(c: dict | None = None) -> Image.Image:
    im, d, fg, ac = base("clean")
    d.text((120, 60), "Software map", font=font(64), fill=ac)
    box_f, small = font(30), font(24, bold=False)
    boxes = {  # name: (x, y, w, h, title, subtitle)
        "phone": (120, 220, 330, 120, "Phone / laptop", "on the tailnet"),
        "capture": (560, 220, 330, 120, "Packet capture", "tshark: SNI, DNS, sizes"),
        "classify": (1000, 220, 380, 120, "Classifier", "3 s windows, one-shot buckets"),
        "trigger": (1490, 220, 310, 120, "Trigger", "2 agreeing steps"),
        "screen": (120, 470, 330, 120, "Mac screen", "10 s chunks"),
        "tribe": (560, 470, 330, 120, "TRIBE v2 (GPU)", "predicted cortical drive"),
        "weights": (1000, 470, 380, 120, "Bucket intensity", "min(your weight, drive)"),
        "relay": (1490, 470, 310, 120, "BLE relay", "Mac / UNO Q"),
        "fun": (120, 730, 330, 120, "Friend's phone", "steering page"),
        "unoq": (560, 730, 330, 120, "UNO Q", "hotspot + page + LEDs"),
        "board": (1490, 730, 310, 150, "GVS board", "ESP32-C3, ≤2 mA\nauto-off after 1 s silence"),
    }
    for name, (x, y, w, h, t, sub) in boxes.items():
        hot = name == "board"
        d.rounded_rectangle([x, y, x + w, y + h], radius=18, outline=ac if hot else fg, width=5 if hot else 3,
                            fill=(255, 250, 244))
        d.text((x + 20, y + 20), t, font=box_f, fill=fg)
        d.multiline_text((x + 20, y + 64), sub, font=small, fill=(90, 86, 80), spacing=8)

    def arrow(a, b, label=""):
        ax, ay, aw, ah = boxes[a][:4]
        bx, by, bw, bh = boxes[b][:4]
        if abs(ay - by) < 10:
            p0, p1 = (ax + aw, ay + ah / 2), (bx, by + bh / 2)
        elif by < ay:  # pointing up: leave from a's top edge, land on b's bottom edge
            p0, p1 = (ax + aw / 2, ay), (bx + bw / 2, by + bh)
        else:
            p0, p1 = (ax + aw / 2, ay + ah), (bx + bw / 2, by)
        d.line([p0, p1], fill=fg, width=4)
        import math
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        for s in (2.6, -2.6):
            d.line([p1, (p1[0] + 22 * math.cos(ang + s), p1[1] + 22 * math.sin(ang + s))], fill=fg, width=4)
        if label:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            if abs(p0[1] - p1[1]) < 20:  # horizontal: centred above the line
                d.text((mx - d.textlength(label, font=small) / 2, my - 36), label, font=small, fill=ac)
            else:                         # vertical: to the right of the line
                d.text((mx + 12, my - 14), label, font=small, fill=ac)

    arrow("phone", "capture"); arrow("capture", "classify"); arrow("classify", "trigger")
    arrow("screen", "tribe"); arrow("tribe", "weights"); arrow("weights", "classify", "how hard")
    arrow("trigger", "relay", "when"); arrow("relay", "board", "Bluetooth")
    arrow("fun", "unoq", "WiFi"); arrow("unoq", "board", "Bluetooth (fun mode)")
    return im


KINDS = {"title": title, "headline": headline, "citations": citations, "results": results,
         "image": image, "software_map": software_map}


def stamp(im: Image.Image, style: str) -> Image.Image:
    """Creator tag bottom right (and logo top right) on every card, matching the CYBER footage."""
    d = ImageDraw.Draw(im)
    fg, ac = STYLES[style][1], STYLES[style][2]
    right = W - 36
    if LOGO:
        lg = Image.open(LOGO).convert("RGBA")
        lg = lg.resize((int(lg.width * 96 / lg.height), 96), Image.LANCZOS)
        if style == "clean":  # dark mark on light cards
            r, g, b, a = lg.split()
            lg = Image.merge("RGBA", (r.point(lambda _: 24), g.point(lambda _: 22), b.point(lambda _: 20), a))
        im.paste(lg, (right - lg.width, H - lg.height - 28), lg)
        right -= lg.width + 18
    if TAG:
        f = ImageFont.truetype(MONO, 36, index=1)
        tw = d.textlength(TAG, font=f)
        ty = H - 28 - 48 - (24 if LOGO else 0)
        d.rectangle([right - tw - 20, ty + 2, right - tw - 14, ty + 46], fill=ac)
        d.text((right - tw, ty), TAG, font=f, fill=fg)
    return im


def render(c: dict, dst: Path) -> Path:
    style = c.get("style", "clean" if c["type"] in ("citations", "results", "image", "software_map") else "dedsec")
    im = KINDS[c["type"]](c)
    (stamp(im, style) if c.get("mark", True) else im).save(dst)  # "mark": false leaves the creator mark off
    return dst


if __name__ == "__main__":
    if sys.argv[1] == "software_map":
        software_map().save(sys.argv[2])
    elif sys.argv[1] == "demo":
        out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
        render({"type": "title", "text": "what if you could edit your reflexes?"}, out / "title.png")
        render({"type": "headline", "text": "Meta to pay up to $18B to settle states' claims it designed apps to addict kids",
                "source": "Reuters / AP, Aug 26 2026"}, out / "headline.png")
        render({"type": "results", "lines": ["Nauseous since 3:30 a.m.", "4 friends felt it with me",
                                              "3 friends drove me like an RC car"]}, out / "results.png")
        render({"type": "software_map"}, out / "software_map.png")
