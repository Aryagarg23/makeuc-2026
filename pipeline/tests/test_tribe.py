"""TRIBE scores cap bucket weights."""
from __future__ import annotations

import json

import pytest
from hypothesis import assume, given, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline import tribe as T
from gvs_pipeline.__main__ import main
from gvs_pipeline.packets import to_line

from test_pipeline import flow

f = st.floats(-1, 1, allow_nan=False)


@given(st.floats(0, 1), f, f, f)
def test_tribe_never_raises_user_weight(w, s, n, h):
    # Reason: TRIBE predicts average-viewer cortical drive, not this person's wish; it may only soften their choice.
    assume(h > n + 1e-6)
    assert 0.0 <= T.capped_weight(w, s, n, h) <= w


@given(f, f, f, f)
def test_drive_monotone_in_score(s1, s2, n, h):
    assume(h > n + 1e-6)
    lo, hi = sorted((s1, s2))
    assert T.drive(lo, n, h) <= T.drive(hi, n, h)


def test_anchors_map_to_ends():
    assert T.drive(0.1, 0.1, 0.5) == 0.0 and T.drive(0.5, 0.1, 0.5) == 1.0


@given(f, f)
def test_inverted_anchors_refused(n, h):
    # Reason: if the high anchor doesn't out-score neutral the scale is meaningless; refuse rather than invert weights.
    assume(h <= n)
    with pytest.raises(ValueError):
        T.drive(0.0, n, h)


def test_nonfinite_score_refused(tmp_path):
    p = tmp_path / "x.tribe.json"
    p.write_text('{"score": NaN}')
    with pytest.raises(ValueError):
        T.load_score(p)


def tj(tmp_path, name, score):
    p = tmp_path / f"{name}.tribe.json"
    p.write_text(json.dumps({"score": score}))
    return str(p)


def test_cli_enroll_with_tribe_caps_and_stores_drive(tmp_path, capsys):
    ex = tmp_path / "reels.tsv"
    ex.write_text("\n".join(to_line(p) for p in flow("9.9.9.9", "v.tiktokv.com", 0.0, 20)) + "\n")
    store = tmp_path / "p.json"
    args = ["--store", str(store), "enroll", "short_video", str(ex), "--weight", "0.9",
            "--tribe", tj(tmp_path, "reels", 0.2), "--tribe-anchors", tj(tmp_path, "n", 0.0), tj(tmp_path, "h", 0.4)]
    assert main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tribe_drive"] == 0.5 and out["weight"] == 0.5 and out["user_weight"] == 0.9
    (b,) = C.load(store)
    assert b.weight == 0.5 and b.tribe_drive == 0.5


def test_cli_tribe_flags_go_together(tmp_path):
    ex = tmp_path / "reels.tsv"
    ex.write_text(to_line(flow("9.9.9.9", "v.tiktokv.com", 0.0, 1)[0]) + "\n")
    with pytest.raises(SystemExit):
        main(["--store", str(tmp_path / "p.json"), "enroll", "b", str(ex), "--weight", "1", "--tribe", tj(tmp_path, "x", 0.1)])
