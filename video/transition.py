"""Glitchy window-cloning transition between two scenes (the frozen-desktop window-drag smear).

  .venv/bin/python transition.py LAST_FRAME.png FIRST_FRAME.png out.mp4 [--seconds 1.6]

The outgoing frame shrinks into a window (generic title bar) that is dragged along a looping path over a
canvas that is never cleared, so it leaves a trail of clones; glitch slices and RGB offsets hit the canvas
in bursts; in the last third the window's content flips to the incoming scene and the clones multiply;
ends on a hard block-glitch frame. Audio: bit-crushed noise stutters and short square blips.
"""
from __future__ import annotations

import argparse
import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, AR = 1920, 1080, 30, 48000
MONO = "/System/Library/Fonts/Menlo.ttc"


def window(content: Image.Image, scale: float, title: str) -> Image.Image:
    w, h = int(W * scale), int(H * scale)
    bar = 34
    win = Image.new("RGB", (w + 6, h + bar + 6), (200, 200, 205))
    d = ImageDraw.Draw(win)
    d.rectangle([0, 0, w + 5, bar], fill=(24, 24, 28))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([12 + i * 22, 10, 26 + i * 22, 24], fill=c)
    d.text((90, 7), title, font=ImageFont.truetype(MONO, 18), fill=(220, 220, 220))
    win.paste(content.resize((w, h)), (3, bar + 3))
    return win


def glitch(arr: np.ndarray, rng: random.Random, strength: float) -> np.ndarray:
    out = arr.copy()
    for _ in range(int(3 + 8 * strength)):
        y0 = rng.randrange(0, H - 30)
        sh = rng.randint(10, int(30 + 120 * strength))
        out[y0:y0 + sh] = np.roll(out[y0:y0 + sh], rng.randint(-int(250 * strength) - 1, int(250 * strength) + 1), axis=1)
    if rng.random() < 0.6 * strength:
        k = rng.randint(4, int(8 + 18 * strength))
        out[..., 0] = np.roll(out[..., 0], k, axis=1)
        out[..., 2] = np.roll(out[..., 2], -k, axis=1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a", type=Path); ap.add_argument("b", type=Path); ap.add_argument("out", type=Path)
    ap.add_argument("--seconds", type=float, default=1.6)
    ap.add_argument("--title", default="agreement_we_just_made.mp4")
    x = ap.parse_args()
    rng = random.Random(4)
    A = Image.open(x.a).convert("RGB").resize((W, H))
    B = Image.open(x.b).convert("RGB").resize((W, H))
    n = int(x.seconds * FPS)
    canvas = A.copy()
    audio = x.out.with_suffix(".wav")
    # audio: stuttering crushed noise + three square blips
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"anoisesrc=d={x.seconds}:c=white:a=0.35:r={AR}",
                    "-f", "lavfi", "-i", f"aevalsrc='0.25*sgn(sin(2*PI*880*t))*lt(mod(t,0.37),0.05)':d={x.seconds}:s={AR}",
                    "-filter_complex", "[0:a]acrusher=bits=3:mode=lin:aa=0,volume='0.9*lt(mod(t,0.13),0.07)':eval=frame[n];"
                    "[1:a]acrusher=bits=4[b];[n][b]amix=inputs=2:normalize=0,afade=t=out:st="
                    f"{x.seconds - 0.15}:d=0.15,aformat=channel_layouts=stereo[o]", "-map", "[o]", str(audio)], check=True)
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
                             "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(x.out)],
                            stdin=subprocess.PIPE)
    for i in range(n):
        u = i / max(1, n - 1)
        scale = 0.92 - 0.47 * min(1.0, u / 0.25)  # shrink fast into a window, then drag
        content = A if u < 0.62 else B
        win = window(content, scale, x.title if u < 0.62 else "loading_next_scene.exe")
        # looping drag path, accelerating; more clones per frame toward the end
        for k in range(1 if u < 0.5 else (2 if u < 0.8 else 4)):
            ph = u * (6 + 10 * u) + k * 0.35
            cx = W / 2 + (W / 2 - win.width / 2 - 20) * math.sin(ph * 1.3)
            cy = H / 2 + (H / 2 - win.height / 2 - 20) * math.sin(ph * 2.1 + 0.7)
            canvas.paste(win, (int(cx - win.width / 2), int(cy - win.height / 2)))
        frame = np.asarray(canvas)
        strength = 0.25 + 0.75 * u
        if i % 4 in (0, 1) or u > 0.85:
            frame = glitch(frame, rng, strength)
        if i == n - 1:  # last frame: hard block glitch
            small = np.asarray(Image.fromarray(frame).resize((W // 40, H // 40), Image.NEAREST))
            frame = np.asarray(Image.fromarray(small).resize((W, H), Image.NEAREST))
        proc.stdin.write(np.ascontiguousarray(frame).tobytes())
    proc.stdin.close()
    proc.wait()
    audio.unlink(missing_ok=True)
    print(f"wrote {x.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
