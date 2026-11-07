"""TRIBE v2 inference on CPU (GPU on this box is held by another service)."""
import resource, sys, time
from pathlib import Path
import numpy as np
import torch

t0 = time.time()
def lap(msg):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    print(f"[{time.time()-t0:7.1f}s] peakRSS={rss:.1f}GB {msg}", flush=True)

torch.set_num_threads(24)
print("cuda visible:", torch.cuda.is_available(), flush=True)
from tribev2 import TribeModel

video = Path(sys.argv[1])
cpu = {
    "data.text_feature.device": "cpu",
    "data.audio_feature.device": "cpu",
    "data.video_feature.image.device": "cpu",
    "data.num_workers": 0,
}
model = TribeModel.from_pretrained("facebook/tribev2", cache_folder="/root/tribev2/cache",
                                   device="cpu", config_update=cpu)
lap("model loaded")
df = model.get_events_dataframe(video_path=video)
lap(f"events built: {df.type.value_counts().to_dict()}")
preds, segments = model.predict(events=df)
lap(f"predicted: preds.shape={preds.shape}")
out = video.with_suffix(".preds.npy")
np.save(out, preds)
print("saved", out, "segment starts:", [round(float(s.start), 2) for s in segments][:20])
print("pred stats: mean %.4f std %.4f min %.4f max %.4f" % (preds.mean(), preds.std(), preds.min(), preds.max()))
