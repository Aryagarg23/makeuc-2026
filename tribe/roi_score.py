"""Summarise TRIBE v2 predictions (T, 20484) on fsaverage5 into Destrieux ROI groups.

Uses nilearn's Destrieux surface atlas (fsaverage5, no licence click-through), not
tribev2.utils.get_hcp_labels, which calls mne.datasets.fetch_hcp_mmp_parcellation(accept=True).
"""
import sys
import numpy as np
from nilearn import datasets

GROUPS = {
    "visual": ["G_cuneus", "S_calcarine", "Pole_occipital", "G_occipital_", "G_and_S_occipital_inf",
               "S_oc_", "S_occipital_ant", "G_oc-temp_lat-fusifor", "G_oc-temp_med-Lingual"],
    "auditory": ["G_temp_sup-G_T_transv", "S_temporal_transverse", "G_temp_sup-Plan_tempo", "G_temp_sup-Lateral"],
    "language": ["S_temporal_sup", "G_temporal_middle", "G_front_inf-Opercular", "G_front_inf-Triangul"],
    "dorsal_attention": ["S_intrapariet_and_P_trans", "G_parietal_sup", "S_precentral-sup-part"],
    "vmpfc_ofc": ["G_rectus", "G_orbital", "S_orbital", "G_subcallosal", "S_suborbital"],
}

def labels_fsaverage5():
    a = datasets.fetch_atlas_surf_destrieux(verbose=0)
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in a["labels"]]
    per_vertex = np.concatenate([np.asarray(a["map_left"]), np.asarray(a["map_right"])])
    assert per_vertex.shape == (20484,), per_vertex.shape
    return names, per_vertex

def group_masks():
    names, pv = labels_fsaverage5()
    masks = {}
    for g, prefixes in GROUPS.items():
        idx = [i for i, n in enumerate(names) if any(n.startswith(p) for p in prefixes)]
        masks[g] = np.isin(pv, idx)
    return masks

def summarise(preds):
    masks = group_masks()
    return {g: preds[:, m].mean(axis=1) for g, m in masks.items()}, {g: int(m.sum()) for g, m in masks.items()}

if __name__ == "__main__":
    preds = np.load(sys.argv[1])
    ts, sizes = summarise(preds)
    print("preds", preds.shape, "vertices per group", sizes)
    print("whole-cortex mean %.4f" % preds.mean())
    for g, x in ts.items():
        print(f"{g:17s} mean {x.mean():+.4f}  per-TR {np.round(x, 3).tolist()}")
