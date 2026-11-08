"""Hyperpop cutout scene: a crude sticker collage over layered kitsch (rays, rainbow, clouds, sea, dolphin,
balloons), a white meme caption band on top, one beat per voiceover line, stickers that match what is said.

  .venv/bin/python hyperpop.py beats.json out.mp4

beats.json = {"voice": {"speaker": "Samantha", "rate": 205, "pitch": 1.1},
              "beats": [{"say": "spoken line", "caption": "meme text (default: say)",
                         "stickers": ["🔥", "📱"], "shout": "NO.", "strings": false, "shake": false,
                         "clutter": 7, "hold": 0.0, "label": "THE ALGORITHM"}]}
Depth: a camera pans continuously and whip-pans on every beat; each layer moves by camera * depth, so the
sky barely moves, clouds drift at two speeds, two sea bands roll past each other (the dolphin jumps between
them), and foreground stickers (some blurred, out of focus) sweep across faster than the main ones.
Stickers never sit still: they enter (pop / slide / drop with overshoot), float, wobble, squash and stretch,
and "boil" (a small stop-motion jitter 8 times a second, motion stepped at 15 fps like a cutout animation).
"strings": a giant hand works a wooden control bar (labelled with "label") and the beat's stickers hang from
it as marionettes: three strings each, they rise and fall with the bar's tilt and jerk on every pull.
The voice is macOS `say` brightened and pitched up toward the chirpy TikTok-TTS sound ("Jessie"); drop a
real recording in with "file" on a beat. A beat lasts its line + 0.18 s + "hold".
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import tempfile
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS, AR = 1920, 1080, 30, 48000
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
ARIAL = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
BAND = 260
SW = W * 2  # width of a tileable background strip
HORIZON = 0.62
_cache: dict = {}


def ease_back(u: float) -> float:
    u = max(0.0, min(1.0, u))
    c1 = 1.70158
    return 1 + (c1 + 1) * (u - 1) ** 3 + c1 * (u - 1) ** 2


def emoji(ch: str) -> Image.Image:
    """One emoji as a sticker: 160 px glyph, white outline, transparent background."""
    if ch in _cache:
        return _cache[ch]
    f = ImageFont.truetype(EMOJI, 160)
    im = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((40, 40), ch, font=f, embedded_color=True)
    a = im.getchannel("A")
    if a.getbbox() is None:
        raise ValueError(f"no glyph for {ch!r} in Apple Color Emoji")
    st = Image.new("RGBA", im.size, (255, 255, 255, 0))
    st.putalpha(a.filter(ImageFilter.MaxFilter(17)))
    st.alpha_composite(im)
    _cache[ch] = st.crop(st.getbbox())
    return _cache[ch]


def blurred(ch: str, scale: float) -> Image.Image:
    """Out-of-focus foreground sticker (cached: fixed scale, no rotation)."""
    key = ("blur", ch, scale)
    if key not in _cache:
        st = emoji(ch)
        s = st.resize((int(st.width * scale), int(st.height * scale)), Image.BILINEAR)
        pad = Image.new("RGBA", (s.width + 60, s.height + 60), (0, 0, 0, 0))
        pad.alpha_composite(s, (30, 30))
        pad = pad.filter(ImageFilter.GaussianBlur(10))
        pad.putalpha(pad.getchannel("A").point(lambda v: int(v * 0.85)))
        _cache[key] = pad
    return _cache[key]


def paste_sticker(canvas: Image.Image, st: Image.Image, cx: float, cy: float, sx: float, sy: float, rot: float) -> None:
    if sx <= 0.02 or sy <= 0.02:
        return
    s = st.resize((max(1, int(st.width * sx)), max(1, int(st.height * sy))), Image.BILINEAR)
    s = s.rotate(rot, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", s.size, (0, 0, 0, 0))
    shadow.putalpha(s.getchannel("A").point(lambda v: int(v * 0.45)))
    x, y = int(cx - s.width / 2), int(cy - s.height / 2)
    canvas.paste(shadow, (x + 12, y + 14), shadow)
    canvas.paste(s, (x, y), s)


# ---------------------------------------------------------------- background layers

def _sky() -> Image.Image:
    if "sky" not in _cache:
        ys = np.linspace(0, 1, H)[:, None]
        top, mid = np.array([60, 150, 235]), np.array([150, 215, 255])
        sea_top, sea_bot = np.array([40, 140, 220]), np.array([5, 45, 120])
        col = np.where(ys < HORIZON, top + (mid - top) * np.clip(ys / HORIZON, 0, 1),
                       sea_top + (sea_bot - sea_top) * np.clip((ys - HORIZON) / (1 - HORIZON), 0, 1))
        rows = np.repeat(col[:, None, :], W, axis=1)
        _cache["sky"] = Image.fromarray(np.clip(rows, 0, 255).astype(np.uint8)).convert("RGBA")
    return _cache["sky"]


def _rainbow() -> Image.Image:
    """Rainbow on a canvas 400 px wider than the frame, cropped by the camera (depth 0.15)."""
    if "rainbow" not in _cache:
        im = Image.new("RGBA", (W + 400, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        colors = [(255, 60, 60), (255, 150, 40), (255, 235, 60), (80, 220, 90), (60, 160, 255), (110, 80, 230),
                  (200, 90, 230)]
        cx, cy = (W + 400) * 0.52, H * 0.78
        for i, c in enumerate(colors):
            r = 760 - i * 30
            d.arc([cx - r, cy - r, cx + r, cy + r], 190, 350, fill=c + (215,), width=30)
        _cache["rainbow"] = im
    return _cache["rainbow"]


def _clouds(name: str, seed: int, n: int, ymin: float, ymax: float, rmin: float, rmax: float) -> Image.Image:
    """Tileable strip of paper-white cutout clouds with an offset shadow; width SW + W so any W-wide crop fits."""
    if name not in _cache:
        rng = random.Random(seed)
        shape = Image.new("L", (SW, H), 0)
        d = ImageDraw.Draw(shape)
        for _ in range(n):
            x, y, r0 = rng.uniform(0, SW), rng.uniform(ymin, ymax), rng.uniform(rmin, rmax)
            for k in range(rng.randint(3, 5)):
                rr = r0 * rng.uniform(0.7, 1.15)
                px, py = x + k * r0 * 0.85, y - (rr * 0.28 if k % 2 else 0)
                for dx in (-SW, 0, SW):
                    d.ellipse([px + dx - rr, py - rr * 0.62, px + dx + rr, py + rr * 0.62], fill=255)
        strip = Image.new("RGBA", (SW, H), (20, 40, 90, 0))
        strip.putalpha(ImageChops.offset(shape, 10, 12).point(lambda v: v * 80 // 255))
        white = Image.new("RGBA", (SW, H), (255, 255, 255, 0))
        white.putalpha(shape.point(lambda v: v * 235 // 255))
        strip.alpha_composite(white)
        ext = Image.new("RGBA", (SW + W, H), (0, 0, 0, 0))
        ext.paste(strip, (0, 0))
        ext.paste(strip.crop((0, 0, W, H)), (SW, 0))
        _cache[name] = ext
    return _cache[name]


def scroll(im: Image.Image, strip: Image.Image, x: float) -> None:
    x0 = int(x) % SW
    im.alpha_composite(strip.crop((x0, 0, x0 + W, H)))


def sea(im: Image.Image, cam: float, t: float, f: float, y0: float, amp: float, wl: float, speed: float,
        col: tuple) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    off = cam * f
    pts = [(x, y0 + amp * math.sin((x + off) / wl + t * speed)) for x in range(-24, W + 48, 24)]
    d.polygon(pts + [(W + 48, H), (-24, H)], fill=col)
    d.line(pts, fill=(255, 255, 255, 210), width=7)


def rays(im: Image.Image, cam: float, t: float) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    cx, cy, R = W * 0.52 - cam * 0.08, H * 0.78, 2600
    for k in range(0, 24, 2):
        a0 = t * 0.25 + k * math.pi / 12
        a1 = a0 + math.pi / 12
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))],
                  fill=(255, 255, 255, 34))


def camera(t: float, starts: list[float]) -> float:
    """Horizontal camera position: a slow pan plus a whip-pan (overshooting) at every beat start."""
    x = 160 * math.sin(0.45 * t) + 60 * math.sin(1.3 * t + 1)
    for i, s in enumerate(starts):
        if t >= s:
            x += 120 * (1 if i % 2 else -1) * ease_back((t - s) / 0.35)
    return x


# ---------------------------------------------------------------- text

def caption_band(im: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, BAND], fill=(255, 255, 255, 255))
    size = 104
    while size > 56:
        f = ImageFont.truetype(ARIAL, size)
        lines = textwrap.wrap(text, int(W / (size * 0.52)))
        if len(lines) <= 3:
            break
        size -= 4
    y = (BAND - len(lines) * (size + 10)) / 2
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text(((W - tw) / 2, y), line, font=f, fill=(0, 0, 0))
        y += size + 10


def shout(im: Image.Image, text: str, t_in: float, t: float) -> None:
    pop = min(1.0, t_in / 0.18)
    size = int(230 * (0.6 + 0.4 * pop + 0.08 * math.sin(t_in * 20) * (t_in < 0.4)))
    f = ImageFont.truetype(IMPACT, size)
    layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, 40), text, font=f, fill=(255, 235, 60), stroke_width=14, stroke_fill=(0, 0, 0))
    layer = layer.rotate(-6 + 3 * math.sin(t * 7), resample=Image.BICUBIC)
    im.alpha_composite(layer, (0, H - 470))


# ---------------------------------------------------------------- stickers

def step(t: float) -> float:
    return math.floor(t * 15) / 15  # cutout motion on twos


def boil(t: float, idx: int) -> random.Random:
    return random.Random(int(t * 8) * 1009 + idx)


def draw_main(im: Image.Image, s: dict, t: float, tin: float, cam: float, idx: int) -> None:
    u = tin - s["delay"]
    if u < 0:
        return
    ts, e, j = step(t), ease_back(u / 0.32), boil(t, idx)
    x, y = s["x"] - cam * s["f"], s["y"]
    sc = s["scale"]
    if s["entry"] == "slide":
        x += s["from"] * (1 - e)
    elif s["entry"] == "drop":
        y -= (y + 300) * (1 - e)
    else:
        sc *= min(1.0, u / 0.16) * (1 + 0.25 * math.sin(min(u, 0.3) / 0.3 * math.pi))
    x += 22 * math.sin(0.8 * ts + s["ph"]) + j.uniform(-4, 4)
    y += 18 * math.sin(2.6 * ts + s["ph"]) + j.uniform(-4, 4)
    sq = 0.07 * math.sin(5 * ts + s["ph"])
    rot = s["rot"] + 9 * math.sin(2.1 * ts + s["ph"]) + j.uniform(-2.5, 2.5)
    paste_sticker(im, emoji(s["ch"]), x, y, sc * (1 + sq), sc * (1 - sq), rot)


def draw_clutter(im: Image.Image, s: dict, t: float, tin: float, cam: float, idx: int) -> None:
    u = tin - s["delay"]
    if u < 0:
        return
    ts, j = step(t), boil(t, idx)
    x = (s["x"] - cam * s["f"] + s["vx"] * t) % (W + 240) - 120 + j.uniform(-3, 3)
    y = s["y"] + 12 * math.sin(2 * ts + s["ph"]) + j.uniform(-3, 3)
    sc = s["scale"] * min(1.0, u / 0.12)
    paste_sticker(im, emoji(s["ch"]), x, y, sc, sc, s["rot"] + s["spin"] * ts)


def draw_fg(im: Image.Image, s: dict, t: float, cam: float) -> None:
    b = blurred(s["ch"], s["scale"])
    x = (s["x"] - cam * s["f"] + s["vx"] * t) % (W + 2 * b.width) - b.width
    y = s["y"] + 16 * math.sin(1.3 * t + s["ph"])
    im.paste(b, (int(x - b.width / 2), int(y - b.height / 2)), b)


def bar_img(label: str) -> Image.Image:
    key = ("bar", label)
    if key not in _cache:
        L, T = 1150, 66
        im = Image.new("RGBA", (L + 30, T + 30), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([16, 18, 16 + L, 18 + T], radius=20, fill=(0, 0, 0, 90))
        d.rounded_rectangle([10, 10, 10 + L, 10 + T], radius=20, fill=(176, 114, 58, 255), outline=(70, 40, 15, 255),
                            width=6)
        f = ImageFont.truetype(IMPACT, 50)
        tw = d.textlength(label, font=f)
        d.text((10 + (L - tw) / 2, 13), label, font=f, fill=(255, 235, 60), stroke_width=4, stroke_fill=(0, 0, 0))
        _cache[key] = im
    return _cache[key]


def draw_rig(im: Image.Image, puppets: list[dict], label: str, t: float, tin: float, cam: float) -> None:
    """A giant hand tilts a control bar; the puppets hang from it on strings and move with every pull."""
    ts = step(t)
    drop = ease_back(tin / 0.3)
    a = math.radians(13 * math.sin(4.2 * t))
    cx = W / 2 + 70 * math.sin(1.6 * t) - cam * 0.35
    by = (BAND - 300) + 520 * drop  # comes down out of the caption band, settles at BAND + 220
    ca, sa = math.cos(a), math.sin(a)

    def on_bar(s: float) -> tuple[float, float]:
        return cx + s * ca, by - s * sa

    strings, bodies = [], []
    for i, p in enumerate(puppets):
        bx, bpy = on_bar(p["s"])
        lower = ease_back((tin - 0.08 * i) / 0.35)
        jig = 30 * abs(math.sin(8 * ts + i * 1.7))  # the jerk on every pull
        x = bx + 14 * math.sin(3 * ts + p["ph"])
        y = H * 0.62 + (bpy - by) * 1.7 - jig - 700 * (1 - lower)
        rot = -math.degrees(a) * 1.5 + 10 * math.sin(5 * ts + i)
        st = emoji(p["ch"])
        w, h = st.width * p["scale"], st.height * p["scale"]
        r = math.radians(rot)
        for ds, (ox, oy) in ((-80, (-0.4 * w, -0.12 * h)), (0, (0, -0.5 * h)), (80, (0.4 * w, -0.12 * h))):
            px = x + ox * math.cos(r) + oy * math.sin(r)
            py = y - ox * math.sin(r) + oy * math.cos(r)
            strings.append((on_bar(p["s"] + ds), (px, py)))
        bodies.append((st, x, y, p["scale"], rot))
    for st, x, y, sc, rot in bodies:
        paste_sticker(im, st, x, y, sc, sc, rot)
    d = ImageDraw.Draw(im, "RGBA")
    for (x0, y0), (x1, y1) in strings:
        d.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, 200), width=8)
        d.line([(x0, y0), (x1, y1)], fill=(20, 20, 20, 255), width=4)
        d.ellipse([x1 - 7, y1 - 7, x1 + 7, y1 + 7], fill=(20, 20, 20, 255))
    hx, hy = cx - 150 * sa, by - 150 * ca  # top of the handle (perpendicular to the bar), where the hand grips
    d.line([(cx, by), (hx, hy)], fill=(70, 40, 15, 255), width=34)
    d.line([(cx, by), (hx, hy)], fill=(176, 114, 58, 255), width=22)
    bar = bar_img(label).rotate(math.degrees(a), expand=True, resample=Image.BICUBIC)
    im.paste(bar, (int(cx - bar.width / 2), int(by - bar.height / 2)), bar)
    paste_sticker(im, emoji("🫳"), hx + 8, hy - 30, 1.7, 1.7, -math.degrees(a) * 0.6)


# ---------------------------------------------------------------- audio

def tts(text: str, dst: Path, v: dict) -> None:
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "raw.aiff"
        subprocess.run(["say", "-v", v.get("speaker", "Samantha"), "-r", str(v.get("rate", 205)), "-o", str(raw), text],
                       check=True)
        p = v.get("pitch", 1.1)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                        f"aresample={AR},asetrate={AR}*{p},aresample={AR},atempo={1 / p:.4f},"
                        "highshelf=f=3500:g=4,acompressor=threshold=0.2:ratio=3,volume=1.4",
                        "-ac", "2", str(dst)], check=True)


def dur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout)


# ---------------------------------------------------------------- plan + render

AMBIENT = ["✨", "💖", "⭐", "💫", "🌈", "💥"]


def plan_beat(i: int, b: dict, rng: random.Random) -> dict:
    n = len(b["stickers"])
    mains, puppets = [], []
    for k, ch in enumerate(b["stickers"]):
        if b.get("strings"):
            puppets.append({"ch": ch, "s": (k - (n - 1) / 2) * 420, "scale": 2.0, "ph": rng.uniform(0, 6)})
        else:
            mains.append({"ch": ch, "x": W * (0.18 + 0.64 * (k + 0.5) / max(1, n)) + rng.uniform(-80, 80),
                          "y": rng.uniform(BAND + 210, H - 290), "scale": rng.uniform(1.8, 2.9),
                          "rot": rng.uniform(-18, 18), "delay": k * 0.12, "ph": rng.uniform(0, 6), "f": 0.35,
                          "entry": ("pop", "slide", "drop")[(k + i) % 3], "from": rng.choice((-1, 1)) * W * 0.7})
    clutter = b.get("clutter", 7)

    def amb(f0, f1, s0, s1, y0, y1, spin):
        return {"ch": rng.choice(AMBIENT), "x": rng.uniform(0, W), "y": rng.uniform(y0, y1), "f": rng.uniform(f0, f1),
                "scale": rng.uniform(s0, s1), "rot": rng.uniform(-30, 30), "spin": rng.uniform(-spin, spin),
                "vx": rng.uniform(-40, 40), "delay": rng.uniform(0, 0.4), "ph": rng.uniform(0, 6)}

    far = [amb(0.15, 0.4, 0.3, 0.55, BAND + 40, H * 0.55, 40) for _ in range(clutter // 2)]
    near = [amb(1.0, 1.4, 0.6, 0.95, BAND + 60, H - 60, 120) for _ in range(clutter - clutter // 2)]
    fg = [{"ch": rng.choice(AMBIENT + b["stickers"]), "x": rng.uniform(0, W), "y": H - 70,
           "f": 1.7, "scale": rng.uniform(2.6, 3.2), "vx": rng.uniform(-70, 70), "ph": rng.uniform(0, 6)}
          for _ in range(0 if b.get("strings") else 2)]  # out-of-focus, bottom edge only; none over the rig
    return {"mains": mains, "puppets": puppets, "far": far, "near": near, "fg": fg}


def frame_at(t: float, beat: dict, cam: float) -> np.ndarray:
    b, tin, p = beat["b"], t - beat["t0"], beat["plan"]
    im = _sky().copy()
    rays(im, cam, t)
    x0 = int(min(400, max(0, 200 + cam * 0.15)))
    im.alpha_composite(_rainbow().crop((x0, 0, x0 + W, H)))
    scroll(im, _clouds("far", 3, 12, BAND + 10, H * 0.42, 35, 60), cam * 0.3 + t * 12)
    scroll(im, _clouds("near", 8, 7, BAND + 80, H * 0.56, 70, 115), cam * 0.7 + t * 34)
    for k, s in enumerate(p["far"]):
        draw_clutter(im, s, t, tin, cam, 100 + k)
    sea(im, cam, t, 0.45, H * HORIZON, 9, 80, 2.2, (60, 150, 230, 150))
    ph = (t % 3.2) / 3.2
    paste_sticker(im, emoji("🐬"), 150 + ph * 560 - cam * 0.6, H * 0.74 - 270 * math.sin(math.pi * ph), 0.9, 0.9,
                  -40 + 80 * ph)
    sea(im, cam, t, 0.9, H * 0.80, 20, 120, -3.1, (10, 70, 165, 235))
    for k, (bx, sp) in enumerate([(220, 40), (1500, 55), (1750, 35), (980, 48)]):
        by = (H * 0.75 - (t * sp + k * 130) % (H * 0.6)) + 60
        bxx = (bx - cam * 1.1) % (W + 200) - 100
        paste_sticker(im, emoji("🎈"), bxx + 30 * math.sin(t + k), by, 0.45, 0.45, 8 * math.sin(t * 2 + k))
    for k, s in enumerate(p["mains"]):
        draw_main(im, s, t, tin, cam, k)
    if p["puppets"]:
        draw_rig(im, p["puppets"], b.get("label", "THE ALGORITHM"), t, tin, cam)
    for k, s in enumerate(p["near"]):
        draw_clutter(im, s, t, tin, cam, 200 + k)
    d = ImageDraw.Draw(im, "RGBA")
    rs = random.Random(5)
    for k in range(60):  # sparkles, front layer
        x = (rs.uniform(0, W * 1.5) - cam * 1.4) % W
        y = rs.uniform(BAND, H)
        a = 0.5 + 0.5 * math.sin(t * 6 + k)
        sz = 4 + 8 * a
        d.line([(x - sz, y), (x + sz, y)], fill=(255, 255, 255, int(255 * a)), width=3)
        d.line([(x, y - sz), (x, y + sz)], fill=(255, 255, 255, int(255 * a)), width=3)
    for s in p["fg"]:
        draw_fg(im, s, t, cam)
    if b.get("shout"):
        shout(im, b["shout"], tin, t)
    z = 1 + 0.07 * max(0.0, 1 - tin / 0.25) ** 2  # punch-in on every beat
    if z > 1.001:
        cw, ch = W / z, H / z
        im = im.crop((int((W - cw) / 2), int((H - ch) / 2), int((W + cw) / 2), int((H + ch) / 2))).resize((W, H))
    caption_band(im, b.get("caption", b["say"]))
    return np.asarray(im.convert("RGB"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("beats", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--only", type=float, nargs="*", help="write these times as PNGs next to out instead of a video")
    a = ap.parse_args()
    spec = json.loads(a.beats.read_text())
    voice = spec.get("voice", {})
    rng = random.Random(11)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        wavs, beats, t0 = [], [], 0.0
        for i, b in enumerate(spec["beats"]):
            w = Path(b["file"]).resolve() if b.get("file") else d / f"l{i:02d}.wav"
            if not b.get("file"):
                tts(b["say"], w, voice)
            length = dur(w) + 0.18 + b.get("hold", 0.0)
            beats.append({"t0": t0, "len": length, "b": b, "plan": plan_beat(i, b, rng)})
            wavs.append((w, length))
            t0 += length
        total, starts = t0, [x["t0"] for x in beats]

        def beat_at(t: float) -> dict:
            return next((x for x in beats if x["t0"] <= t < x["t0"] + x["len"]), beats[-1])

        if a.only:
            for t in a.only:
                png = a.out.with_name(f"{a.out.stem}_{t:05.2f}.png")
                Image.fromarray(frame_at(t, beat_at(t), camera(t, starts))).save(png)
                print(png)
            return 0
        vo = d / "vo.wav"
        inputs, filt = [], []
        for i, (w, length) in enumerate(wavs):
            inputs += ["-i", str(w)]
            filt.append(f"[{i}:a]aresample={AR},aformat=channel_layouts=stereo,apad=whole_dur={length:.3f}[a{i}]")
        filt.append("".join(f"[a{i}]" for i in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[a]")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filt),
                        "-map", "[a]", str(vo)], check=True)
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(vo), "-map", "0:v", "-map", "1:a",
                                 "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                 "-c:a", "aac", "-b:a", "192k", "-shortest", str(a.out)], stdin=subprocess.PIPE)
        shake = random.Random(13)
        for fi in range(int(total * FPS)):
            t = fi / FPS
            beat = beat_at(t)
            frame = frame_at(t, beat, camera(t, starts))
            if beat["b"].get("shake") and t - beat["t0"] < 0.5:
                frame = np.roll(frame, (shake.randint(-14, 14), shake.randint(-14, 14)), axis=(0, 1))
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        proc.stdin.close()
        proc.wait()
    print(f"wrote {a.out} ({total:.1f}s, {len(beats)} beats)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
