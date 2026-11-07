"""Render the time-mean TRIBE prediction on fsaverage5 (left/right lateral) to PNG."""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from nilearn import datasets, plotting

preds = np.load(sys.argv[1]); out = sys.argv[2]
fs = datasets.fetch_surf_fsaverage("fsaverage5")
m = preds.mean(0); n = m.shape[0] // 2
fig, axes = plt.subplots(1, 2, subplot_kw={"projection": "3d"}, figsize=(8, 3.5))
for ax, hemi, data in [(axes[0], "left", m[:n]), (axes[1], "right", m[n:])]:
    plotting.plot_surf_stat_map(fs[f"infl_{hemi}"], data, hemi=hemi, view="lateral",
                                bg_map=fs[f"sulc_{hemi}"], axes=ax, colorbar=False, cmap="cold_hot",
                                vmax=float(np.percentile(np.abs(m), 99)))
fig.savefig(out, dpi=110, bbox_inches="tight"); print("wrote", out)
