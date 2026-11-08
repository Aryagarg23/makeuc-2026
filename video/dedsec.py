"""Scene 2 in the hacker-collective look of scene 1: black screen, glitch-decoded keywords, 1-bit dithered
stencil icons for what is said, a terminal-typed caption, LED-glyph eyes, block-glitch bursts, and a
glitched voice.

  .venv/bin/python dedsec.py beats.json out.mp4 [--only T T ...]   (--only: write PNG frames instead)

beats.json = {"voice": {"speaker": "Daniel", "rate": 180, "pitch": 0.78},
              "beats": [{"say": "spoken line", "caption": "text (default: say)", "key": "BIG WORD",
                         "stickers": ["🔥"], "shout": "NO.", "strings": false, "shake": false, "hold": 0.0,
                         "label": "THE ALGORITHM"}]}
"shout" overrides "key".
Picture, back to front: a huge dim ghost of the beat's first icon drifting slowly; small dim icons drifting
at mid depth; the keyword; the icons (white ordered-dither stencils with a pink offset copy, scanning in top
to bottom, jittering 8 times a second) each with its Unicode name as a small label; the typed caption; a
pink ticker of all the keywords along the bottom; corner brackets, header and LED eyes. A slow camera sway
moves each layer by its own depth. Block-glitch bursts on beat starts.
"strings": a stencil hand tilts a control bar labelled "label"; the beat's icons hang from it on strings.
"feral": "word": after the line, that word is screamed (shrill, many overlapped rushed copies) while the
screen fills with the word, re-laid out every frame; the beat ends hard on the scream's last sample.
Voice: macOS `say`, a copy pitched down to 0.78 under the original (the masked double voice). Glitches follow
the speech instead of landing at random: word onsets are found from the loudness envelope (log-energy rises of 9 dB), one or two words
per line stutter their first syllable ("th-th-thermonuclear", 8 ms fades so nothing clicks), and one stretch
gets a short sample-and-hold crush blended under the dry voice. A light constant texture (soft crush,
chorus, small room) runs under everything so the glitches belong to the voice. A beat lasts its line +
0.12 s + "hold".
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cyber
import hyperpop as hp

W, H, FPS, AR = 1920, 1080, 30, 48000
PINK, WHITE, GREY, DIM = (255, 60, 150), (238, 238, 238), (120, 120, 120), (30, 30, 36)  # RGB
HN, MONO = "/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Menlo.ttc"
SCRAMBLE = "#$%&@!/\\<>01?*+=_"
_cache: dict = {}


# ---------------------------------------------------------------- voice

def ff(args: list[str], data: bytes | None = None) -> bytes:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], input=data,
                          capture_output=True, check=True).stdout


def onsets(x: np.ndarray) -> list[int]:
    """Sample indices of syllable onsets: the 10 ms log-energy rises >= 9 dB above its minimum over the last
    80 ms, within 30 dB of the line's peak; 150 ms refractory. The line's first sound always counts."""
    hop = AR // 100
    n = len(x) // hop
    e = 10 * np.log10(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-10)
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    floor = e.max() - 30
    out, last = [], -100
    for i in range(1, n):
        if e[i] < floor:
            continue
        if not out and e[i - 1] < floor:  # first sound of the line
            out.append(max(0, (i - 1) * hop)); last = i
        elif i - last >= 15 and e[i] - e[max(0, i - 8):i].min() >= 9:
            out.append(max(0, (i - 2) * hop)); last = i
    return out


def fade(s: np.ndarray, ms: float = 8) -> np.ndarray:
    n = min(len(s) // 2, int(AR * ms / 1000))
    s = s.copy()
    if n:
        r = np.linspace(0, 1, n, dtype=np.float32)
        s[:n] *= r
        s[-n:] *= r[::-1]
    return s


def organic_glitch(x: np.ndarray, rng: random.Random) -> np.ndarray:
    """One or two syllable stutters at detected onsets, one crush blended under a later syllable."""
    ons = [o for o in onsets(x) if o < len(x) - int(AR * 0.15)]
    x = x.copy()
    if len(ons) > 2:  # crush first, on the original timeline, 60 ms into a later syllable
        a = rng.choice(ons[1:]) + int(AR * 0.06)
        seg = x[a:a + int(AR * 0.12)]
        if len(seg) > 200:
            held = np.round(np.repeat(seg[::8], 8)[:len(seg)] * 10) / 10
            x[a:a + len(seg)] = 0.45 * seg + 0.55 * fade(held, 10)
    picks = sorted(rng.sample(ons, min(len(ons), rng.choice([1, 2])))) if ons else []
    out, i = [], 0
    for p in picks:
        out.append(x[i:p])
        syl = x[p:p + int(AR * rng.uniform(0.06, 0.085))]
        for g in [0.55, 0.8][: rng.choice([1, 2])]:  # the syllable's start once or twice, rising, then the word
            out.append(fade(syl) * g)
        i = p
    out.append(x[i:])
    return np.concatenate(out).astype(np.float32)


def glitch_voice(text: str, dst: Path, v: dict, seed: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "raw.aiff"
        subprocess.run(["say", "-v", v.get("speaker", "Daniel"), "-r", str(v.get("rate", 180)), "-o", str(raw), text],
                       check=True)
        p = v.get("pitch", 0.78)
        pcm = ff(["-i", str(raw), "-filter_complex",
                  f"[0:a]aresample={AR},asplit[a][b];[a]asetrate={AR}*{p},aresample={AR},atempo={1 / p:.4f}[lo];"
                  "[b]volume=0.45[hi];[lo][hi]amix=inputs=2:normalize=0,highpass=f=90",
                  "-f", "f32le", "-ac", "1", "-ar", str(AR), "-"])
        x = organic_glitch(np.frombuffer(pcm, np.float32).copy(), random.Random(seed))
        ff(["-f", "f32le", "-ac", "1", "-ar", str(AR), "-i", "-", "-af",
            "acrusher=bits=10:mode=log:aa=1:mix=0.25,chorus=0.7:0.9:22|31:0.25|0.2:0.3|0.4:1.5|2,"
            "aecho=0.8:0.35:38|61:0.16|0.09,lowpass=f=9500,acompressor=threshold=0.15:ratio=3,"
            "volume=7.5,alimiter=limit=0.95",
            "-ac", "2", str(dst)], x.tobytes())


def feral(word: str, dst: Path, seed: int, copies: int = 11) -> float:
    """A shrill, feral, overlapped scream of one word: `say` copies pitched up 1.35-2.1x (which also rushes
    them), rasped (fast vibrato), crushed and clipped, stacked 30-80 ms apart with random pans, over one
    pitched-down growl; tanh-saturated. Returns the length in seconds."""
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "w.aiff"
        subprocess.run(["say", "-v", "Daniel", "-r", "260", "-o", str(raw), word], check=True)
        layers = [(0.0, 0.7, 0.62, 0.5)] + [(0.0, rng.uniform(1.35, 2.1), rng.uniform(0.55, 1.0), rng.uniform(0, 1))
                                             for _ in range(copies)]
        off, starts = 0.0, []
        for k in range(len(layers)):
            starts.append(0.0 if k == 0 else off)
            off += rng.uniform(0.03, 0.08)
        tracks = []
        for (_, pitch, gain, pan), st in zip(layers, starts):
            pcm = ff(["-i", str(raw), "-af",
                      f"aresample={AR},silenceremove=start_periods=1:start_threshold=0.01,asetrate={AR}*{pitch:.3f},"
                      f"aresample={AR},highpass=f=180,vibrato=f={rng.uniform(14, 24):.1f}:d=0.55,"
                      "acrusher=bits=5:mode=log:aa=0:mix=0.6,volume=5,asoftclip=type=hard",
                      "-f", "f32le", "-ac", "1", "-ar", str(AR), "-"])
            x = np.frombuffer(pcm, np.float32) * gain
            tracks.append((int(st * AR), x, pan))
        n = max(o + len(x) for o, x, _ in tracks)
        mix = np.zeros((n, 2), np.float32)
        for o, x, pan in tracks:
            mix[o:o + len(x), 0] += x * math.cos(pan * math.pi / 2)
            mix[o:o + len(x), 1] += x * math.sin(pan * math.pi / 2)
        mix = np.tanh(2.2 * mix / max(1e-6, np.abs(mix).max()))
        mix[-int(AR * 0.01):] *= np.linspace(1, 0, int(AR * 0.01), dtype=np.float32)[:, None]
        mix = (mix / np.abs(mix).max() * 0.65).astype(np.float32)  # ~ -14 dB mean, a few dB over the speech
        ff(["-f", "f32le", "-ac", "2", "-ar", str(AR), "-i", "-", str(dst)], mix.tobytes())
    return n / AR


def scream_frame(t: float, word: str) -> np.ndarray:
    """The word everywhere at once, a new layout every frame, glitched and shaken."""
    r = random.Random(int(t * FPS) * 13 + 1)
    im = Image.new("RGB", (W, H), (8, 8, 10))
    d = ImageDraw.Draw(im)
    for _ in range(16):
        f = ImageFont.truetype(HN, r.choice([110, 170, 240, 340, 460]), index=9)
        d.text((r.uniform(-200, W - 100), r.uniform(-120, H - 120)), word, font=f,
               fill=r.choice([WHITE, PINK, (70, 70, 80)]))
    f = ImageFont.truetype(HN, 640, index=9)
    tw = d.textlength(word, font=f)
    x, y = (W - tw) / 2 + r.uniform(-40, 40), 120 + r.uniform(-30, 30)
    d.text((x - 16, y + 10), word, font=f, fill=PINK)
    d.text((x, y), word, font=f, fill=WHITE)
    fr = np.array(im)
    bgr = cv2.cvtColor(fr, cv2.COLOR_RGB2BGR)
    fr = cv2.cvtColor(cyber.glitch(bgr, r.choice(["blocks", "blocks", "photocopy"]), r), cv2.COLOR_BGR2RGB)
    s = r.randint(10, 26)
    fr[..., 0] = np.roll(fr[..., 0], s, axis=1)
    fr[..., 2] = np.roll(fr[..., 2], -s, axis=1)
    return np.roll(fr, (r.randint(-24, 24), r.randint(-24, 24)), axis=(0, 1))


# ---------------------------------------------------------------- stencils

def stencil(ch: str, height: int) -> np.ndarray:
    """Bool mask: the emoji as an ordered-dither stencil with a solid silhouette edge."""
    key = (ch, height)
    if key not in _cache:
        st = hp.emoji(ch)
        s = st.resize((int(st.width * height / st.height), height), Image.BILINEAR)
        arr = np.asarray(s)
        alpha = arr[..., 3] > 110
        lum = cv2.cvtColor(arr[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        cell = max(5, height // 60)
        hs, ws = max(1, lum.shape[0] // cell), max(1, lum.shape[1] // cell)
        small = cv2.resize(lum, (ws, hs), interpolation=cv2.INTER_AREA)
        tile = np.tile(cyber.BAYER, (hs // 4 + 1, ws // 4 + 1))[:hs, :ws]
        dots = cv2.resize(((small * 1.15) > tile).astype(np.uint8), (lum.shape[1], lum.shape[0]),
                          interpolation=cv2.INTER_NEAREST).astype(bool)
        a8 = alpha.astype(np.uint8)
        k = max(9, height // 35)
        edge = alpha & ~cv2.erode(a8, np.ones((k, k), np.uint8)).astype(bool)
        _cache[key] = (dots & alpha) | edge
    return _cache[key]


def put(canvas: np.ndarray, mask: np.ndarray, cx: float, cy: float, color, reveal: float = 1.0) -> None:
    mh, mw = mask.shape
    x0, y0 = int(cx - mw / 2), int(cy - mh / 2)
    rows = int(mh * max(0.0, min(1.0, reveal)))
    if rows <= 0:
        return
    m = mask[:rows]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + mw), min(H, y0 + rows)
    if xa >= xb or ya >= yb:
        return
    sub = m[ya - y0:yb - y0, xa - x0:xb - x0]
    canvas[ya:yb, xa:xb][sub] = color
    if reveal < 1.0 and y0 + rows < H:  # bright scan line at the reveal edge
        canvas[max(0, y0 + rows - 2):y0 + rows + 1, xa:xb] = PINK


def icon(canvas: np.ndarray, ch: str, height: int, cx: float, cy: float, t: float, idx: int, reveal: float) -> None:
    j = random.Random(int(t * 8) * 1009 + idx)
    m = stencil(ch, height)
    if j.random() < 0.12:  # a sliced row band slips sideways now and then
        m = m.copy()
        y, hh = j.randrange(0, m.shape[0] - 10), j.randint(6, 30)
        m[y:y + hh] = np.roll(m[y:y + hh], j.randint(-30, 30), axis=1)
    cx += j.uniform(-3, 3)
    cy += j.uniform(-3, 3) + 8 * math.sin(2.2 * t + idx)
    put(canvas, m, cx + 8, cy + 5, PINK, reveal)
    put(canvas, m, cx, cy, WHITE, reveal)


def name_of(ch: str) -> str:
    try:
        return unicodedata.name(ch[0])
    except ValueError:
        return "UNKNOWN"


# ---------------------------------------------------------------- text

def fit(text: str, path: str, index: int, maxw: int, size: int) -> ImageFont.FreeTypeFont:
    while size > 40:
        f = ImageFont.truetype(path, size, index=index)
        if f.getlength(text) <= maxw:
            return f
        size -= 8
    return ImageFont.truetype(path, size, index=index)


def decoded(text: str, tin: float, rng: random.Random) -> str:
    """Characters resolve left to right over 0.4 s; unresolved ones are random symbols."""
    out = []
    for i, c in enumerate(text):
        if c == " " or tin >= 0.08 + 0.32 * i / max(1, len(text)):
            out.append(c)
        else:
            out.append(rng.choice(SCRAMBLE))
    return "".join(out)


# ---------------------------------------------------------------- puppet rig

def label_mask(label: str) -> np.ndarray:
    key = ("label", label)
    if key not in _cache:
        f = ImageFont.truetype(MONO, 44, index=1)
        w = int(f.getlength(label)) + 8
        im = Image.new("L", (w, 60), 0)
        ImageDraw.Draw(im).text((4, 2), label, font=f, fill=255)
        _cache[key] = np.asarray(im)
    return _cache[key]


def rig(canvas: np.ndarray, puppets: list[str], label: str, t: float, tin: float, cam: float) -> None:
    ts = math.floor(t * 15) / 15
    a = math.radians(13 * math.sin(4.2 * t))
    ca, sa = math.cos(a), math.sin(a)
    cx = W / 2 + 70 * math.sin(1.6 * t) + cam
    by = -120 + 450 * hp.ease_back(tin / 0.3)  # lowers into frame, settles at y 330
    L, T = 560, 30
    u, nrm = np.array([ca, -sa]), np.array([sa, ca])
    c = np.array([cx, by])

    def on_bar(s: float) -> tuple[float, float]:
        return cx + s * ca, by - s * sa

    hgt = 250
    for i, ch in enumerate(puppets):
        s = (i - (len(puppets) - 1) / 2) * 420
        bx, bpy = on_bar(s)
        lower = hp.ease_back((tin - 0.08 * i) / 0.35)
        x = bx + 14 * math.sin(3 * ts + i)
        y = 700 + (bpy - by) * 1.7 - 30 * abs(math.sin(8 * ts + i * 1.7)) - 700 * (1 - lower)
        m = stencil(ch, hgt)
        w = m.shape[1]
        for ds, (ox, oy) in ((-80, (-0.4 * w, -0.12 * hgt)), (0, (0, -0.5 * hgt)), (80, (0.4 * w, -0.12 * hgt))):
            p0 = tuple(int(v) for v in on_bar(s + ds))
            p1 = (int(x + ox), int(y + oy))
            cv2.line(canvas, p0, p1, WHITE, 3, cv2.LINE_AA)
            cv2.circle(canvas, p1, 6, PINK, -1, cv2.LINE_AA)
        icon(canvas, ch, hgt, x, y, t, 50 + i, 1.0)
    handle = c - 150 * nrm  # perpendicular handle up from the bar's middle
    cv2.line(canvas, tuple(c.astype(int)), tuple(handle.astype(int)), WHITE, 10, cv2.LINE_AA)
    corners = np.array([c - L * u - T * nrm, c + L * u - T * nrm, c + L * u + T * nrm, c - L * u + T * nrm], np.int32)
    cv2.fillPoly(canvas, [corners], (14, 14, 16), cv2.LINE_AA)
    cv2.polylines(canvas, [corners], True, WHITE, 4, cv2.LINE_AA)
    lm = label_mask(label)
    rot = cv2.getRotationMatrix2D((lm.shape[1] / 2, lm.shape[0] / 2), math.degrees(a), 1.0)
    big = max(lm.shape) + 20
    rot[:, 2] += [(big - lm.shape[1]) / 2, (big - lm.shape[0]) / 2]
    lr = cv2.warpAffine(lm, rot, (big, big)) > 120
    put(canvas, lr, cx, by, PINK)
    icon(canvas, "🫳", 190, handle[0] + 6, handle[1] - 60, t, 99, 1.0)


# ---------------------------------------------------------------- frames

def eyes(canvas: np.ndarray, pair: tuple[str, str]) -> None:
    x, y = W - 150, 62
    canvas[y - 26:y + 26, x - 96:x + 96] = (0, 0, 0)
    cv2.rectangle(canvas, (x - 96, y - 26), (x + 96, y + 26), GREY, 1)
    bgr = canvas[..., ::-1].copy()
    cyber.led(bgr, pair[0], x - 44, y, 8)
    cyber.led(bgr, pair[1], x + 44, y, 8)
    canvas[:] = bgr[..., ::-1]


def brackets(canvas: np.ndarray) -> None:
    m, n = 28, 70
    for (x, y, dx, dy) in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
        cv2.line(canvas, (x, y), (x + dx * n, y), WHITE, 2)
        cv2.line(canvas, (x, y), (x, y + dy * n), WHITE, 2)


def ticker(canvas: np.ndarray, text: str, t: float) -> None:
    key = ("ticker", text)
    if key not in _cache:
        f = ImageFont.truetype(MONO, 26, index=1)
        unit = text + "   //   "
        w = int(f.getlength(unit))
        im = Image.new("L", (w * 3, 40), 0)
        ImageDraw.Draw(im).text((0, 5), unit * 3, font=f, fill=255)
        _cache[key] = (np.asarray(im) > 120, w)
    mask, w = _cache[key]
    y0 = H - 72
    canvas[y0:y0 + 40, :] = PINK
    off = int(t * 140) % w
    seg = mask[:, off:off + W]
    canvas[y0:y0 + 40, :seg.shape[1]][seg] = (8, 8, 10)


def frame_at(t: float, beat: dict, nb: int, noise: list[np.ndarray], keys: str) -> np.ndarray:
    b, tin, k = beat["b"], t - beat["t0"], beat["i"]
    if beat.get("scream_at") is not None and tin >= beat["scream_at"]:
        return scream_frame(t, b["feral"].upper())
    cam = 40 * math.sin(0.5 * t) + 18 * math.sin(1.3 * t)
    fr = np.full((H, W, 3), (8, 8, 10), np.uint8)
    sts = b["stickers"]
    # back: one huge dim ghost of the first icon, drifting; then small dim icons at mid depth
    g = stencil(sts[0], 900)
    put(fr, g, W * 0.72 + cam * 0.25 - 25 * tin, H * 0.52, DIM)
    for j in range(6):
        r = random.Random(k * 97 + j)
        ch = sts[j % len(sts)]
        x = (r.uniform(0, W) + cam * 0.6 + r.uniform(-30, 30) * t) % (W + 200) - 100
        put(fr, stencil(ch, r.choice([70, 90, 110])), x, r.uniform(160, H - 160), (52, 52, 60))
    im = Image.fromarray(fr)
    d = ImageDraw.Draw(im)
    f_hdr = ImageFont.truetype(MONO, 24)
    d.text((60, 46), f"// TRANSMISSION_02   [{k + 1:02d}/{nb:02d}]", font=f_hdr, fill=GREY)
    d.line([(60, 84), (420, 84)], fill=PINK, width=3)
    key = (b.get("shout") or b.get("key") or "").upper()
    if key and not b.get("strings"):
        f = fit(key, HN, 9, 1720, 250)
        txt = decoded(key, tin, random.Random(int(t * 30) * 7 + k))
        tw = d.textlength(txt, font=f)
        x, y = (W - tw) / 2 + cam * 0.5, 115
        d.text((x - 8, y + 6), txt, font=f, fill=PINK)
        d.text((x, y), txt, font=f, fill=WHITE)
    cap = b.get("caption", b["say"])
    n = int(len(cap) * min(1.0, tin / max(0.3, beat["speak"] * 0.85)))
    f_cap = fit(cap, MONO, 0, 1640, 46)
    shown = cap[:n] + ("█" if int(t * 4) % 2 == 0 or n < len(cap) else " ")
    d.text(((W - f_cap.getlength(cap)) / 2, 912), shown, font=f_cap, fill=WHITE)
    f_lbl = ImageFont.truetype(MONO, 22, index=1)
    if not b.get("strings"):
        hgt = 360 if len(sts) <= 3 else 300
        xs = [W * (0.5 + (i - (len(sts) - 1) / 2) * (0.66 / max(1, len(sts) - 1) if len(sts) > 1 else 0))
              for i in range(len(sts))]
        for i, (ch, cx) in enumerate(zip(sts, xs)):
            if tin > 0.3 + 0.1 * i:
                lbl = f"[{name_of(ch)}]"
                d.text((cx + cam - f_lbl.getlength(lbl) / 2, 600 + hgt / 2 + 18), lbl, font=f_lbl, fill=PINK)
    fr = np.array(im)
    fr = cv2.add(fr, noise[int(t * FPS) % len(noise)])
    if b.get("strings"):
        rig(fr, sts, b.get("label", "THE ALGORITHM"), t, tin, cam)
    else:
        for i, (ch, cx) in enumerate(zip(sts, xs)):
            icon(fr, ch, hgt, cx + cam, 600, t, i + 10 * k, (tin - 0.1 - 0.1 * i) / 0.22)
    ticker(fr, keys, t)
    brackets(fr)
    eyes(fr, cyber.PAIRS[k % len(cyber.PAIRS)])
    fr[::3] = (fr[::3] * 0.82).astype(np.uint8)  # faint scanlines
    gr = random.Random(int(t * FPS) * 31 + 5)
    if tin < 0.17 or beat["burst"](t):
        bgr = cv2.cvtColor(fr, cv2.COLOR_RGB2BGR)
        kind = "photocopy" if (b.get("shake") and tin < 0.07) else "blocks"
        fr = cv2.cvtColor(cyber.glitch(bgr, kind, gr), cv2.COLOR_BGR2RGB)
    if b.get("shake") and tin < 0.5:
        s = gr.randint(6, 14)
        fr[..., 0] = np.roll(fr[..., 0], s, axis=1)
        fr[..., 2] = np.roll(fr[..., 2], -s, axis=1)
        fr = np.roll(fr, (gr.randint(-10, 10), gr.randint(-10, 10)), axis=(0, 1))
    return fr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("beats", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--only", type=float, nargs="*")
    a = ap.parse_args()
    spec = json.loads(a.beats.read_text())
    voice = spec.get("voice", {})
    noise = [np.random.default_rng(s).integers(0, 12, (H, W, 3), dtype=np.uint8) for s in range(6)]
    keys = "   //   ".join((b.get("shout") or b.get("key") or b.get("label") or "").strip('"').upper()
                           for b in spec["beats"])
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        beats, wavs, t0 = [], [], 0.0
        for i, b in enumerate(spec["beats"]):
            w = Path(b["file"]).resolve() if b.get("file") else d / f"l{i:02d}.wav"
            if not b.get("file"):
                glitch_voice(b["say"], w, voice, seed=100 + i)
            scream_at = None
            if b.get("feral"):  # the line, then the word screamed; the beat ends hard on the scream's last sample
                scream_at = hp.dur(w)
                fw = d / f"f{i:02d}.wav"
                feral(b["feral"], fw, seed=900 + i)
                joined = d / f"j{i:02d}.wav"
                ff(["-i", str(w), "-i", str(fw), "-filter_complex",
                    f"[0:a]aresample={AR},aformat=channel_layouts=stereo[a];[1:a]aresample={AR},"
                    "aformat=channel_layouts=stereo[b];[a][b]concat=n=2:v=0:a=1[o]", "-map", "[o]", str(joined)])
                w = joined
            speak = hp.dur(w)
            length = speak + (0.0 if scream_at is not None else 0.12) + b.get("hold", 0.0)
            br = random.Random(500 + i)
            spots = [br.uniform(0.8, max(0.9, length - 0.3)) for _ in range(int(length // 2.4))]
            beats.append({"i": i, "t0": t0, "len": length, "speak": scream_at or speak, "b": b, "scream_at": scream_at,
                          "burst": (lambda tt, s0=t0, sp=spots: any(0 <= tt - s0 - x < 0.14 for x in sp))})
            wavs.append((w, length))
            t0 += length
        total = t0

        def beat_at(t: float) -> dict:
            return next((x for x in beats if x["t0"] <= t < x["t0"] + x["len"]), beats[-1])

        if a.only:
            for t in a.only:
                png = a.out.with_name(f"{a.out.stem}_{t:05.2f}.png")
                Image.fromarray(frame_at(t, beat_at(t), len(beats), noise, keys)).save(png)
                print(png)
            return 0
        vo = d / "vo.wav"
        inputs, filt = [], []
        for i, (w, length) in enumerate(wavs):
            inputs += ["-i", str(w)]
            filt.append(f"[{i}:a]aresample={AR},aformat=channel_layouts=stereo,apad=whole_dur={length:.3f}[a{i}]")
        filt.append("".join(f"[a{i}]" for i in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[a]")
        ff([*inputs, "-filter_complex", ";".join(filt), "-map", "[a]", str(vo)])
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(vo), "-map", "0:v", "-map", "1:a",
                                 "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                 "-c:a", "aac", "-b:a", "192k", "-shortest", str(a.out)], stdin=subprocess.PIPE)
        for fi in range(int(total * FPS)):
            t = fi / FPS
            proc.stdin.write(np.ascontiguousarray(frame_at(t, beat_at(t), len(beats), noise, keys)).tobytes())
        proc.stdin.close()
        proc.wait()
    print(f"wrote {a.out} ({total:.1f}s, {len(beats)} beats)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
