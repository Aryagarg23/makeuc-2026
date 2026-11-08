"""Looks and voices for the pitch video. Every output is 1920x1080, 30 fps, H.264 + AAC 48 kHz stereo.

  .venv/bin/python fx.py look  IN OUT --look kids|dedsec|clean [--eyes] [--in S --out S]
  .venv/bin/python fx.py voice IN OUT --voice meme|echo|meme+echo|tts-crush     (audio of a clip)
  .venv/bin/python fx.py tts   "text" OUT.wav [--speaker Zarvox]                (robot narrator)

KIDS   soft bloom, oversaturated, VHS grain, 4:3 picture in a round vignette (the toddler-TV feel).
DEDSEC restrained: mostly monochrome, contrast up, light grain, soft vignette; --eyes pixelates a band
       over every detected face's eyes (OpenCV Haar cascade, 4.x).
CYBER  restrained hacker-cutscene look drawn per frame (cyber.py: mono footage, burst glitches, LED eyes, moods): LED-glyph eyes, face brackets, scrolling data side
       bars, status line. --crop X Y W H cuts the source first (e.g. a reposter's burned-in headline).
MEME   pitch up 1.6x at the same speed.  ECHO  three fading repeats.  TTS  macOS `say`, bit-crushed.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

W, H, FPS, AR = 1920, 1080, 30, 48000
NORM = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={FPS}"

LOOKS = {
    "clean": NORM,
    "kids": (
        "scale=1440:1080:force_original_aspect_ratio=increase,crop=1440:1080,"
        "eq=saturation=1.75:brightness=0.05:contrast=1.06,split[a][b];[b]gblur=sigma=14[bl];"
        "[a][bl]blend=all_mode=screen:all_opacity=0.45,noise=alls=14:allf=t+u,"
        "rgbashift=rh=2:bh=-2,vignette=angle=PI/3.2,"
        f"pad={W}:{H}:240:0:color=black,setsar=1,fps={FPS}"
    ),
    # cyber.py does the picture, type and glitch bursts; this only adds a little grain and a soft vignette
    "cyber": f"{NORM},noise=alls=5:allf=t",  # no vignette: it dimmed the corner tag and title
    # restrained: mostly monochrome, contrast up, light grain (the heavy RGB-split/tears grade read as deep-fried)
    "dedsec": f"{NORM},hue=s=0.25,eq=contrast=1.12:brightness=-0.01,noise=alls=5:allf=t",
}

VOICES = {
    "orig": "anull",
    "meme": f"asetrate={AR}*1.6,aresample={AR},atempo=0.625",
    "echo": "aecho=0.8:0.9:350|700|1050:0.55|0.35|0.2",
    "meme+echo": f"asetrate={AR}*1.6,aresample={AR},atempo=0.625,aecho=0.8:0.9:350|700|1050:0.55|0.35|0.2",
    "tts-crush": "acrusher=bits=8:mode=log:aa=1:mix=0.6,aecho=0.8:0.6:35:0.3,highpass=f=110",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def has_audio(path: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def pixelate_eyes(src: Path, dst: Path, start: float | None, end: float | None, block: int = 14) -> int:
    """Write src's frames to dst (video only) with a pixelated band over each face's eyes. Returns faces seen."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    idx = 0  # frame-accurate start (cv2 seeks land on the previous keyframe): decode and count from 0
    while start and idx / fps < start - 1e-6:
        if not cap.grab():
            break
        idx += 1
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    faces, held, seen, n = [], 0, 0, 0
    while True:
        if end is not None and idx / fps >= end - 1e-6:
            break
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if n % 3 == 0:  # detect every 3rd frame, hold boxes in between so the bar doesn't flicker
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(w // 20, w // 20))
            if len(found):
                faces, held = list(found), 0
            elif held < 6:
                held += 1
            else:
                faces = []
        for (x, y, fw, fh) in faces:
            y0, y1 = y + int(0.18 * fh), y + int(0.52 * fh)
            x0, x1 = max(0, x - int(0.05 * fw)), min(w, x + fw + int(0.05 * fw))
            roi = frame[y0:y1, x0:x1]
            if roi.size:
                small = cv2.resize(roi, (max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)))
                frame[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
            seen += 1
        out.write(frame)
        n += 1
    cap.release()
    out.release()
    return seen


def look(src: Path, dst: Path, name: str, eyes: bool = False, start: float | None = None,
         end: float | None = None, voice: str = "orig", crop=None, label: str = "SCAN", subs=None,
         moods=None, hud=None, pins=None, nofaces=None, titles=None, tag="+- II", logo=None,
         names=None) -> None:
    vf = LOOKS[name]
    trim = (["-ss", str(start)] if start else []) + (["-to", str(end)] if end is not None else [])
    with tempfile.TemporaryDirectory() as d:
        vsrc, vtrim = src, trim
        if name == "cyber":  # picture, type, eyes and glitch bursts frame by frame (cyber.py); LOOKS["cyber"] adds grain
            import cyber
            vsrc = Path(d) / "cyber.mp4"
            n = cyber.render(src, vsrc, start, end, tuple(crop) if crop else None, label,
                             subs=tuple(subs) if subs else None, moods=moods, hud=hud, pins=pins, nofaces=nofaces,
                             titles=titles, tag=tag, logo=logo, names=names)
            print(f"cyber: LED eyes on {n} face-frames in {src.name}")
            vtrim = []
        elif eyes:
            vsrc = Path(d) / "eyes.mp4"
            n = pixelate_eyes(src, vsrc, start, end)
            print(f"eyes: pixelated {n} face-frames in {src.name}")
            vtrim = []
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *vtrim, "-i", str(vsrc)]
        audio = has_audio(src)
        if audio:
            cmd += [*trim, "-i", str(src)]
        else:
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r={AR}:cl=stereo"]
        cmd += ["-filter_complex", f"[0:v]{vf}[v];[1:a]aresample={AR},aformat=channel_layouts=stereo,{VOICES[voice]}[a]",
                "-map", "[v]", "-map", "[a]", "-shortest",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(AR), str(dst)]
        run(cmd)


def voice(src: Path, dst: Path, name: str) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-c:v", "copy",
         "-af", f"aresample={AR},{VOICES[name]}", "-c:a", "aac", "-b:a", "192k", str(dst)])


def tts(text: str, dst: Path, speaker: str = "Zarvox", rate: int = 165) -> None:
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "raw.aiff"
        run(["say", "-v", speaker, "-r", str(rate), "-o", str(raw), text])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
             "-af", f"aresample={AR},{VOICES['tts-crush']}", "-ac", "2", str(dst)])


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("look")
    a.add_argument("src", type=Path); a.add_argument("dst", type=Path)
    a.add_argument("--look", choices=LOOKS, default="clean"); a.add_argument("--eyes", action="store_true")
    a.add_argument("--crop", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    a.add_argument("--subs", type=int, nargs=4, metavar=("X", "Y", "W", "H"),
                   help="caption strip outside the picture, keyed and laid over the bottom of the crop")
    a.add_argument("--in", dest="start", type=float); a.add_argument("--out", dest="end", type=float)
    a.add_argument("--voice", choices=VOICES, default="orig")
    v = sub.add_parser("voice")
    v.add_argument("src", type=Path); v.add_argument("dst", type=Path); v.add_argument("--voice", choices=VOICES, required=True)
    t = sub.add_parser("tts")
    t.add_argument("text"); t.add_argument("dst", type=Path); t.add_argument("--speaker", default="Zarvox")
    x = ap.parse_args()
    if x.cmd == "look":
        look(x.src, x.dst, x.look, x.eyes, x.start, x.end, x.voice, x.crop, subs=x.subs)
    elif x.cmd == "voice":
        voice(x.src, x.dst, x.voice)
    else:
        tts(x.text, x.dst, x.speaker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
