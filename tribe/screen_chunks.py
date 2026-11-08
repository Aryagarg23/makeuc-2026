"""Record the Mac screen (+ mic) in fixed chunks and send each to the TRIBE server.

  pipeline/.venv/bin/python tribe/screen_chunks.py [--seconds 10] [--out tribe/live]
  (or open tribe/start_screen_chunks.command, so Terminal holds the Screen Recording permission)

Needs the scoring server reachable at http://127.0.0.1:8770 (tribe/serve.py on the GPU box, via
`ssh -N -L 8770:127.0.0.1:8770 wsl`). Appends one JSON line per scored chunk to <out>/scores.jsonl:
  {"t0": epoch, "t1": epoch, "score": float, "groups": {...}, "wall_s": float, "lag_s": float}
t0/t1 are wall-clock epoch seconds, the same clock as tshark's frame.time_epoch, so the pipeline
can line a chunk up with what the network classifier decided over the same seconds.
Chunks are deleted after scoring. Audio comes from the microphone (what the room hears), because
macOS has no system-audio capture without a loopback driver.
"""
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

SCREEN = "Capture screen 0"
MIC = "MacBook Pro Microphone"
SERVER = "http://127.0.0.1:8770"


def record(path: Path, seconds: int) -> tuple[float, float]:
    t0 = time.time()
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "avfoundation", "-capture_cursor", "1", "-framerate", "15", "-i", f"{SCREEN}:{MIC}",
         "-t", str(seconds), "-vf", "scale=640:-2,format=yuv420p",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ac", "1", str(path)],
        check=True)
    return t0, time.time()


def score(path: Path) -> dict:
    req = urllib.request.Request(SERVER + "/score", data=path.read_bytes(),
                                 headers={"Content-Type": "video/mp4"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=10)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "live")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / "scores.jsonl"
    with urllib.request.urlopen(SERVER + "/health", timeout=10) as r:
        print("server:", r.read().decode().strip(), flush=True)

    todo: queue.Queue = queue.Queue(maxsize=3)  # if TRIBE falls behind, drop old chunks, keep recent

    def worker():
        while True:
            path, t0, t1 = todo.get()
            try:
                out = score(path)
                rec = {"t0": round(t0, 3), "t1": round(t1, 3), "score": out["score"], "groups": out["groups"],
                       "wall_s": out["wall_s"], "lag_s": round(time.time() - t1, 1)}
                with log.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                print(f"{time.strftime('%H:%M:%S')} chunk {time.strftime('%H:%M:%S', time.localtime(t0))} "
                      f"score {out['score']:+.4f} lag {rec['lag_s']}s", flush=True)
            except Exception as e:
                print("score failed:", e, flush=True)
            finally:
                path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    i = 0
    while True:
        p = a.out / f"chunk{i % 6}.mp4"
        t0, t1 = record(p, a.seconds)
        if todo.full():
            old = todo.get_nowait()
            old[0].unlink(missing_ok=True)
            print("TRIBE behind: dropped a chunk", flush=True)
        todo.put((p, t0, t1))
        i += 1


if __name__ == "__main__":
    raise SystemExit(main())
