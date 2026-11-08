"""TRIBE v2 scoring server for the GPU box. Loads the model once, scores uploaded clips.

Run in WSL inside the TRIBE venv, from the folder holding score_clip.py / roi_score.py:
  cd ~/tribev2/gvs && nohup ../.venv/bin/python serve.py > serve.log 2>&1 &

  GET  /health  -> {"ok": true, "device": "cuda", "loaded": true}
  POST /score   body = mp4 bytes -> {"score", "groups", "seconds", "wall_s"}

Listens on 127.0.0.1:8770 only. From the Mac: ssh -N -L 8770:127.0.0.1:8770 wsl
(WSL2 forwards its localhost to the Windows host's localhost, which the ssh tunnel reaches).
One clip at a time. score = drive() from score_clip.py: mean predicted response over the
visual, auditory and dorsal-attention vertices. Predicted cortical drive, not reward.
"""
import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_clip import drive  # noqa: E402

HOST, PORT = "127.0.0.1", 8770
MAX_BYTES = 200 * 1024 * 1024
lock = threading.Lock()
state = {"model": None, "device": None}


def load() -> None:
    import torch
    from tribev2 import TribeModel

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # Llama-3.2-3B in fp32 is ~12.8 GB; on a 24 GB card next to V-JEPA2-g it spilled into Windows shared
    # memory and video encoding slowed from 3.5 s to 50 s per step (serve.log, 2026-11-08). A 10 s clip has
    # a few words, so the text model runs on CPU and the GPU is left to the video and audio models.
    cfg = {"data.text_feature.device": "cpu"}
    t0 = time.time()
    state["model"] = TribeModel.from_pretrained(
        "facebook/tribev2", cache_folder=str(Path.home() / "tribev2" / "cache"), device=dev, config_update=cfg)
    state["device"] = dev
    print(f"model loaded on {dev} in {time.time() - t0:.1f}s", flush=True)


def score_file(clip: Path) -> dict:
    t0 = time.time()
    m = state["model"]
    df = m.get_events_dataframe(video_path=clip)
    preds, _ = m.predict(events=df)
    preds = np.asarray(preds)
    score, groups = drive(preds)
    return {"score": score, "groups": groups, "seconds": int(preds.shape[0]), "wall_s": round(time.time() - t0, 2)}


class H(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = (json.dumps(obj) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "device": state["device"], "loaded": state["model"] is not None})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/score":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_BYTES:
            return self._json(400, {"error": f"body must be 1..{MAX_BYTES} bytes of mp4"})
        data = self.rfile.read(n)
        with tempfile.TemporaryDirectory() as d, lock:
            clip = Path(d) / "clip.mp4"
            clip.write_bytes(data)
            try:
                out = score_file(clip)
            except Exception as e:
                print("score failed:", repr(e), flush=True)
                return self._json(500, {"error": repr(e)})
        print(json.dumps({k: out[k] for k in ("score", "seconds", "wall_s")}), flush=True)
        self._json(200, out)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    load()
    print(f"serving on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
