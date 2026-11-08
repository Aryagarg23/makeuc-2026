"""Assemble the pitch video from an edit list.

  .venv/bin/python build.py edl.json out/pitch.mp4

edl.json = {"music": {"file": "clips/falle.mp3", "gain": 0.3, "start": 0, "fade_out": 3},   (optional bed,
            ducked under voice and clip audio)
            "segments": [ ... ]}, each segment is either a clip or a card:
  {"src": "clips/scroll.mp4", "in": 2.0, "out": 8.5,
   "look": "kids"|"dedsec"|"clean"|"cyber", "eyes": true,
   "crop": [x, y, w, h], "subs": [x, y, w, h],      (cyber: crop the picture, lay a caption strip back over it)
   "moods": [{"from": s, "to": s, "side": "left"|"right"|"any", "words": [...]}],   (cyber: mood readout by shot,
   "hud": [{"from": s, "to": s, "text": "..."}],                                      source seconds)
   "pins": [{"from": s, "to": s, "rect": [x, y, w, h]}],   (cyber: face search region, fractions of the picture)
   "nofaces": [{"from": s, "to": s}],                       (cyber: detection off, e.g. wide shots)
   "titles": [{"from": s, "to": s, "title": "...", "sub": "..."}],   (cyber: lower-third title, top left)
Top level also takes "tag" (creator tag, default "+- II") and "logo" (path to a PNG, top right).
   "audio": "orig"|"mute"|"meme"|"echo"|"meme+echo",
   "vo": {"file": "vo/scene2.wav"} | {"tts": "words", "speaker": "Zarvox"}, "vo_gain": 1.0, "bed_gain": 0.35,
   "note": "free text, ignored"}
  {"card": {<cards.py card>}, "dur": 4.0, "look": "dedsec", "vo": {...}}
A card lasts max(dur, voiceover length + 0.3 s). A clip keeps its own length; voiceover is laid over it
(the clip's own audio is ducked to bed_gain while it plays) and cut at the clip's end.
Every segment is rendered to 1920x1080/30/AAC 48k first, so the final join is a lossless concat.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cards
import fx

HERE = Path(__file__).resolve().parent


def dur(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def vo_file(seg: dict, work: Path, i: int) -> Path | None:
    vo = seg.get("vo")
    if not vo:
        return None
    if "file" in vo:
        return (HERE / vo["file"]).resolve()
    p = work / f"vo{i:02d}.wav"
    fx.tts(vo["tts"], p, vo.get("speaker", "Zarvox"))
    return p


edl_tag, edl_logo = "+- II", None  # set from the edit list's top-level "tag" / "logo"


def render_segment(seg: dict, i: int, work: Path) -> Path:
    look = seg.get("look", "clean")
    base = work / f"base{i:02d}.mp4"
    vo = vo_file(seg, work, i)
    if "card" in seg:
        png = cards.render(seg["card"], work / f"card{i:02d}.png")
        length = max(seg.get("dur", 3.0), (dur(vo) + 0.3) if vo else 0)
        still = work / f"still{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png),
                        "-f", "lavfi", "-i", f"anullsrc=r={fx.AR}:cl=stereo", "-t", f"{length:.3f}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fx.FPS), "-c:a", "aac", str(still)],
                       check=True)
        fx.look(still, base, look)
    else:
        audio = seg.get("audio", "orig")
        fx.look((HERE / seg["src"]).resolve(), base, look, seg.get("eyes", False), seg.get("in"), seg.get("out"),
                "orig" if audio == "mute" else audio, crop=seg.get("crop"), subs=seg.get("subs"),
                moods=seg.get("moods"), hud=seg.get("hud"), pins=seg.get("pins"),
                nofaces=seg.get("nofaces"), titles=seg.get("titles"), tag=edl_tag, logo=edl_logo)
        if audio == "mute":
            muted = work / f"muted{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(base), "-c:v", "copy",
                            "-af", "volume=0", "-c:a", "aac", str(muted)], check=True)
            base = muted
    if not vo:
        return base
    out = work / f"seg{i:02d}.mp4"
    bed, gain = seg.get("bed_gain", 0.35), seg.get("vo_gain", 1.0)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(base), "-i", str(vo),
                    "-filter_complex",
                    f"[0:a]volume={bed}[b];[1:a]aresample={fx.AR},aformat=channel_layouts=stereo,volume={gain}[v];"
                    "[b][v]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def main(edl_path: str, out_path: str) -> int:
    global edl_tag, edl_logo
    edl = json.loads(Path(edl_path).read_text())
    edl_tag = edl.get("tag", "+- II")
    edl_logo = str((HERE / edl["logo"]).resolve()) if edl.get("logo") else None
    cards.TAG, cards.LOGO = edl_tag, edl_logo
    work = HERE / "work" / "build"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, seg in enumerate(edl["segments"]):
        p = render_segment(seg, i, work)
        print(f"segment {i:02d}: {seg.get('look', 'clean'):6s} {dur(p):5.1f}s  {seg.get('note', '')}", flush=True)
        parts.append(p)
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    music = edl.get("music")
    joined = out if not music else work / "joined.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(joined)], check=True)
    if music:
        # music bed under everything, ducked (sidechain) whenever the programme has voice or clip audio
        total = dur(joined)
        g, fade = music.get("gain", 0.3), music.get("fade_out", 3.0)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(joined),
                        "-ss", str(music.get("start", 0)), "-i", str((HERE / music["file"]).resolve()),
                        "-filter_complex",
                        f"[0:a]asplit[p][key];[1:a]aresample={fx.AR},aformat=channel_layouts=stereo,volume={g},"
                        f"afade=t=in:d=1.5,afade=t=out:st={max(0, total - fade):.2f}:d={fade}[m];"
                        "[m][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];"
                        "[p][md]amix=inputs=2:duration=first:normalize=0[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], check=True)
    print(f"wrote {out} ({dur(out):.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
