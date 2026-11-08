"""CYBER look, after the hacker-collective cutscenes in the reference (clean monochrome footage, glitch only as
punctuation, small crisp type, LED-mask eyes). Frame by frame with OpenCV + Pillow; fx.py adds only light grain.

Per frame:
  - optional crop of the source, fit to 1920x1080 (pillarboxed if narrower), mostly desaturated, contrast lifted
  - optional caption strip from outside the picture, keyed and laid back over its bottom (60% width)
  - every face: thin white corner brackets, a small mono tag, a black eye band with white LED glyph eyes
    (X ^ ? <> o -) that change every ~0.7 s, and an optional MOOD readout (by shot, from the edit list)
  - glitch bursts of 5-9 frames: on every shot cut and every 3-6 s otherwise. Kinds: sliced block
    pixelation with sideways offsets, 1-bit photocopy threshold with a pink tint, ordered-dither halftone.
Faces: Haar frontal + profile cascades (opencv 4.x), every 3rd frame; editor-pinned search regions for misses.
Nothing here recognises anyone: who a face is comes from the edit list's shot ranges.
"""
from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
PINK = (255, 60, 150)       # RGB, for Pillow
WHITE = (240, 240, 240)
GREY = (150, 150, 150)
SANS = "/System/Library/Fonts/HelveticaNeue.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"

GLYPHS = {
    "X": ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "^": ["..#..", ".#.#.", "#...#", ".....", "....."],
    "?": [".###.", "#...#", "..##.", ".....", "..#.."],
    "<": ["...#.", "..#..", ".#...", "..#..", "...#."],
    ">": [".#...", "..#..", "...#.", "..#..", ".#..."],
    "o": [".###.", "#...#", "#...#", "#...#", ".###."],
    "-": [".....", ".....", "#####", ".....", "....."],
}
PAIRS = [("X", "X"), ("^", "^"), ("?", "?"), (">", "<"), ("o", "o"), ("-", "-")]
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def led(canvas: np.ndarray, glyph: str, cx: int, cy: int, cell: int) -> None:
    glow = np.zeros_like(canvas)
    x0, y0 = cx - 5 * cell // 2, cy - 5 * cell // 2
    for r, row in enumerate(GLYPHS[glyph]):
        for c, ch in enumerate(row):
            if ch == "#":
                p = (x0 + c * cell + cell // 2, y0 + r * cell + cell // 2)
                cv2.circle(glow, p, max(2, int(cell * 0.42)), (245, 245, 245), -1, cv2.LINE_AA)
    cv2.add(canvas, cv2.GaussianBlur(glow, (0, 0), sigmaX=max(2, cell * 0.6)) // 2, canvas)
    cv2.add(canvas, glow, canvas)


def overlay_subs(pic: np.ndarray, band: np.ndarray, width: float = 0.6) -> None:
    """Key the white caption text out of a black caption strip and lay it over the bottom of pic, outlined."""
    ph, pw = pic.shape[:2]
    tw = int(pw * width)
    band = cv2.resize(band, (tw, int(band.shape[0] * tw / band.shape[1])), interpolation=cv2.INTER_AREA)
    pad = (pw - tw) // 2
    band = cv2.copyMakeBorder(band, 0, 0, pad, pw - tw - pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    text = (cv2.cvtColor(band, cv2.COLOR_BGR2GRAY) > 90).astype(np.uint8)
    if not text.any():
        return
    ys = np.where(text.any(axis=1))[0]
    band, text = band[ys.min():ys.max() + 1], text[ys.min():ys.max() + 1]
    y0 = ph - band.shape[0] - int(ph * 0.06)
    outline = cv2.dilate(text, np.ones((5, 5), np.uint8)).astype(bool)
    roi = pic[y0:y0 + band.shape[0]]
    roi[outline] = (roi[outline] * 0.1).astype(np.uint8)
    roi[text.astype(bool)] = 235


def glitch(img: np.ndarray, kind: str, rng: random.Random) -> np.ndarray:
    h, w = img.shape[:2]
    if kind == "blocks":  # sliced block pixelation, slices pushed sideways
        out = img.copy()
        for _ in range(rng.randint(3, 7)):
            y0 = rng.randrange(0, h - 40)
            sh = rng.randint(20, h // 6)
            blk = rng.choice([16, 24, 32, 48])
            sl = out[y0:y0 + sh]
            small = cv2.resize(sl, (max(1, w // blk), max(1, sl.shape[0] // blk)), interpolation=cv2.INTER_AREA)
            sl = cv2.resize(small, (w, sl.shape[0]), interpolation=cv2.INTER_NEAREST)
            out[y0:y0 + sh] = np.roll(sl, rng.randint(-w // 10, w // 10), axis=1)
        return out
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if kind == "photocopy":  # 1-bit threshold, pink ink on black
        bw = (gray > rng.randint(90, 140)).astype(bool)
        out = np.zeros_like(img)
        out[bw] = (150, 60, 255)  # BGR pink
        return out
    cell = 4  # halftone: ordered dither at a coarse cell
    small = cv2.resize(gray, (w // cell, h // cell), interpolation=cv2.INTER_AREA) / 255.0
    tile = np.tile(BAYER, (small.shape[0] // 4 + 1, small.shape[1] // 4 + 1))[:small.shape[0], :small.shape[1]]
    dots = (small > tile).astype(np.uint8) * 235
    return cv2.cvtColor(cv2.resize(dots, (w, h), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)


def render(src: Path, dst: Path, start: float | None = None, end: float | None = None,
           crop: tuple[int, int, int, int] | None = None, label: str = "SUBJECT", seed: int = 7,
           subs: tuple[int, int, int, int] | None = None, moods: list | None = None, hud: list | None = None,
           pins: list | None = None, nofaces: list | None = None, titles: list | None = None,
           tag: str | None = "+- II", logo: str | None = None, intro_burst: bool = True) -> int:
    """moods: [{"from","to","side": "left"|"right"|"any","words": [...]}] in SOURCE seconds, by shot.
    hud: [{"from","to","text"}] screen-level readout. pins: [{"from","to","rect": [x,y,w,h]}] search regions
    (fractions of the picture) for faces the full-frame detector misses. nofaces: [{"from","to"}] spans with
    detection off (wide shots, where lights and screens read as faces); pins still apply there."""
    moods, hud, pins, nofaces, titles = moods or [], hud or [], pins or [], nofaces or [], titles or []
    logo_im = None
    if logo:  # creator logo, top right, 90 px tall, alpha kept
        logo_im = Image.open(logo).convert("RGBA")
        logo_im = logo_im.resize((int(logo_im.width * 96 / logo_im.height), 96), Image.LANCZOS)
    label = "SUBJECT" if label == "SCAN" else label
    rng = random.Random(seed)
    frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    f_tag, f_mood_l = ImageFont.truetype(MONO, 22), ImageFont.truetype(MONO, 18)
    f_mood = ImageFont.truetype(SANS, 40, index=1)
    f_hud, f_status = ImageFont.truetype(MONO, 34, index=1), ImageFont.truetype(MONO, 18)
    f_title, f_sub, f_tagf = ImageFont.truetype(SANS, 44, index=1), ImageFont.truetype(MONO, 22), ImageFont.truetype(MONO, 36, index=1)
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    # No cap.set seek: OpenCV lands on the keyframe before `start`, so pictures ran ahead of the labels and of
    # the ffmpeg-trimmed audio. Decode from 0 and count frames; source time = frame index / fps.
    src_idx = 0
    while start and src_idx / fps < start - 1e-6:
        if not cap.grab():
            break
        src_idx += 1
    out = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    faces, held, n, seen = [], 0, 0, 0
    pinned_box: dict = {}
    misses: dict = {}
    pair = rng.choice(PAIRS)
    # a cut into this segment from the previous one gets a burst on its first frames, like any other cut
    prev_small, burst_left, burst_kind = None, (6 if intro_burst else 0), "blocks"
    next_burst = int(fps * rng.uniform(2.5, 4.0))

    def detect(gray, min_size):
        f = frontal.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8, minSize=(min_size, min_size))
        if len(f):
            return list(f)
        f = profile.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8, minSize=(min_size, min_size))
        if len(f):
            return list(f)
        fl = profile.detectMultiScale(cv2.flip(gray, 1), scaleFactor=1.1, minNeighbors=8, minSize=(min_size, min_size))
        return [(gray.shape[1] - x - w, y, w, h) for (x, y, w, h) in fl]

    while True:
        if end is not None and src_idx / fps >= end - 1e-6:
            break
        ok, frame = cap.read()
        if not ok:
            break
        now = src_idx / fps
        src_idx += 1
        band = None
        if subs:
            x, y, w, h = subs
            band = frame[y:y + h, x:x + w].copy()
        if crop:
            x, y, w, h = crop
            frame = frame[y:y + h, x:x + w]
        fh, fw = frame.shape[:2]
        s = min(W / fw, H / fh)
        pic = cv2.resize(frame, (int(fw * s), int(fh * s)), interpolation=cv2.INTER_LANCZOS4)
        ph, pw = pic.shape[:2]
        ox, oy = (W - pw) // 2, (H - ph) // 2
        # mostly monochrome, a little colour left in, contrast lifted
        gray3 = cv2.cvtColor(cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        clean_pic = cv2.convertScaleAbs(cv2.addWeighted(pic, 0.22, gray3, 0.78, 0), alpha=1.18, beta=6)
        pic = clean_pic.copy()
        if band is not None:
            overlay_subs(pic, band)

        # shot cut -> burst; otherwise every 3-6 s
        small = cv2.resize(cv2.cvtColor(clean_pic, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32)
        cut = prev_small is not None and float(np.mean(np.abs(small - prev_small))) > 28
        prev_small = small
        if burst_left == 0 and (cut or n >= next_burst):
            burst_left = rng.randint(5, 9)
            burst_kind = rng.choice(["blocks", "blocks", "photocopy", "halftone"])
            next_burst = n + int(fps * rng.uniform(3.0, 6.0))

        if n % 3 == 0:
            gray = cv2.equalizeHist(cv2.cvtColor(clean_pic, cv2.COLOR_BGR2GRAY))
            found = [f for f in detect(gray, pw // 22) if f[1] + f[3] / 2 < 0.55 * ph]
            if found:
                faces, held = [tuple(int(v) for v in f) for f in found], 0
            elif held < 6:
                held += 1
            else:
                faces = []
        if any(z["from"] <= now < z["to"] for z in nofaces):
            faces = []
        live_pins = [p for p in pins if p["from"] <= now < p["to"]]
        if live_pins:
            faces = []
            g = cv2.equalizeHist(cv2.cvtColor(clean_pic, cv2.COLOR_BGR2GRAY))
            for p in live_pins:
                rx, ry = int(p["rect"][0] * pw), int(p["rect"][1] * ph)
                rw, rh = int(p["rect"][2] * pw), int(p["rect"][3] * ph)
                roi = g[ry:ry + rh, rx:rx + rw]
                hit = None
                for casc, flip in ((frontal, False), (profile, False), (profile, True)):
                    img = cv2.flip(roi, 1) if flip else roi
                    f = casc.detectMultiScale(img, scaleFactor=1.08, minNeighbors=3, minSize=(rw // 6, rw // 6))
                    if len(f):
                        x, y, w, h = max(f, key=lambda b: b[2] * b[3])
                        hit = (rx + (rw - x - w if flip else x), ry + y, w, h)
                        break
                key, last = id(p), pinned_box.get(id(p))
                if hit and last and (abs(hit[0] - last[0]) > 0.35 * last[2] or abs(hit[1] - last[1]) > 0.35 * last[3]
                                     or abs(hit[2] - last[2]) > 0.4 * last[2]):
                    hit = None
                if hit:
                    pinned_box[key] = tuple(int(0.4 * a + 0.6 * b) for a, b in zip(last, hit)) if last else hit
                    misses[key] = 0
                else:
                    misses[key] = misses.get(key, 0) + 1
                    if misses[key] > int(fps):
                        pinned_box.pop(key, None)
                if key in pinned_box:
                    faces.append(pinned_box[key])
        if n % max(1, int(fps * 0.7)) == 0:
            pair = rng.choice(PAIRS)
        order = sorted(range(len(faces)), key=lambda i: faces[i][0])
        face_mood = {}
        for m in moods:
            if m["from"] <= now < m["to"] and order:
                idx = order if m.get("side", "any") == "any" else [order[0] if m["side"] == "left" else order[-1]]
                for i in idx:
                    face_mood[i] = m["words"][int(now / 1.2) % len(m["words"])]

        canvas = np.zeros((H, W, 3), np.uint8)
        canvas[oy:oy + ph, ox:ox + pw] = pic
        boxes = []
        for k, (x, y, w, h) in enumerate(faces):
            x, y = x + ox, y + oy
            b0, b1 = y + int(0.27 * h), y + int(0.47 * h)
            cv2.rectangle(canvas, (x + w // 12, b0), (x + w - w // 12, b1), (8, 8, 8), -1)
            cell = max(3, w // 22)
            led(canvas, pair[0], x + int(0.32 * w), (b0 + b1) // 2, cell)
            led(canvas, pair[1], x + int(0.68 * w), (b0 + b1) // 2, cell)
            L = max(14, w // 6)
            for (px, py, dx, dy) in ((x - 8, y - 8, 1, 1), (x + w + 8, y - 8, -1, 1), (x - 8, y + h + 8, 1, -1),
                                     (x + w + 8, y + h + 8, -1, -1)):
                cv2.line(canvas, (px, py), (px + dx * L, py), (240, 240, 240), 2, cv2.LINE_AA)
                cv2.line(canvas, (px, py), (px, py + dy * L), (240, 240, 240), 2, cv2.LINE_AA)
            boxes.append((k, x, y, w, h))
            seen += 1

        bursting = burst_left > 0
        if bursting:
            canvas = glitch(canvas, burst_kind, rng)
            burst_left -= 1

        # type, drawn crisp with Pillow (left off photocopy/halftone frames)
        im = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(im)
        if not (bursting and burst_kind in ("photocopy", "halftone")):  # labels, hud, titles
            for k, x, y, w, h in boxes:
                d.text((x - 8, y - 40), f"{label} {k + 1:02d}", font=f_tag, fill=WHITE)
                if k in face_mood:
                    mx, my = x + w + 30, y + 4
                    need = 30 + d.textlength(face_mood[k], font=f_mood)
                    if mx + need > W - 20:  # no room on the right: put the readout on the left of the box
                        mx = x - 30 - need
                    d.rectangle([mx, my, mx + 4, my + 76], fill=PINK)
                    d.text((mx + 16, my), "MOOD", font=f_mood_l, fill=GREY)
                    d.text((mx + 14, my + 24), face_mood[k], font=f_mood, fill=WHITE)
            for hd in hud:
                if hd["from"] <= now < hd["to"]:
                    tw = d.textlength(hd["text"], font=f_hud)
                    d.rectangle([(W - tw) / 2 - 18, 52, (W + tw) / 2 + 18, 104], fill=(10, 10, 10))
                    d.rectangle([(W - tw) / 2 - 18, 52, (W - tw) / 2 - 12, 104], fill=PINK)
                    d.text(((W - tw) / 2, 58), hd["text"], font=f_hud, fill=WHITE)
            for t in titles:  # lower-third style title, top left, while the span is live
                if t["from"] <= now < t["to"]:
                    tw = max(d.textlength(t["title"], font=f_title), d.textlength(t.get("sub", ""), font=f_sub))
                    panel = Image.new("RGBA", (int(tw) + 60, 112), (6, 6, 6, 205))
                    im.paste(panel, (40, 32), panel)
                    d.rectangle([40, 32, 46, 144], fill=PINK)
                    d.text((62, 40), t["title"], font=f_title, fill=WHITE)
                    d.text((64, 100), t.get("sub", ""), font=f_sub, fill=GREY)
        # creator mark, bottom right on every frame (bursts included): ingot logo with the +- II tag to its left
        right = W - 36
        if logo_im is not None:
            im.paste(logo_im, (right - logo_im.width, H - logo_im.height - 28), logo_im)
            right -= logo_im.width + 18
        if tag:
            tw = d.textlength(tag, font=f_tagf)
            ty = H - 28 - 48 - (24 if logo_im is not None else 0)
            d.rectangle([right - tw - 20, ty + 2, right - tw - 14, ty + 46], fill=PINK)
            d.text((right - tw, ty), tag, font=f_tagf, fill=(255, 255, 255))
        out.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
        n += 1
    cap.release()
    out.release()
    return seen
