"""Live TRIBE scores update bucket weights, credited to what the network saw at the time."""
from __future__ import annotations

import json

from hypothesis import given, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline import tribe_live as TL


def bucket(w=0.9):
    return C.Bucket("ig_reels", w, {"cdninstagram.com"}, (0.5,) * 6, {}, 3.0)


@given(st.floats(0, 1), st.lists(st.floats(0, 1), min_size=1, max_size=20))
def test_live_tribe_never_raises_user_weight(w, drives):
    # Reason: TRIBE scores an average viewer's cortex; it may only soften the user's own choice.
    b = bucket(w)
    for d in drives:
        TL.apply(b, d)
        assert 0 <= b.weight <= w and b.user_weight == w


def test_smoothing_moves_halfway():
    b = bucket(1.0)
    TL.apply(b, 0.2)
    TL.apply(b, 0.6)
    assert abs(b.tribe_drive - 0.4) < 1e-9 and abs(b.weight - 0.4) < 1e-9


def test_attribution_needs_majority_of_overlapping_windows():
    # Reason: one stray reels window inside a minute of DMs must not hand that minute's drive to reels.
    a = TL.Attributor(3.0)
    for t in range(100, 112):
        a.note(float(t), "ig_reels" if t < 109 else None)
    assert a.bucket_for(100.0, 110.0) == "ig_reels"
    b = TL.Attributor(3.0)
    for t in range(100, 112):
        b.note(float(t), "ig_reels" if t == 105 else None)
    assert b.bucket_for(100.0, 110.0) is None


def test_no_windows_no_attribution():
    assert TL.Attributor(3.0).bucket_for(0.0, 10.0) is None


def test_feed_reads_only_new_complete_lines(tmp_path):
    p = tmp_path / "scores.jsonl"
    p.write_text(json.dumps({"t0": 1, "t1": 2, "score": 0.1}) + "\n")
    f = TL.Feed(p)  # starts at the end: old chunks are not replayed
    assert f.new() == []
    with p.open("a") as fh:
        fh.write(json.dumps({"t0": 3, "t1": 4, "score": 0.2}) + "\n" + '{"t0": 5, "t1"')
    assert [r["t0"] for r in f.new()] == [3]
    with p.open("a") as fh:
        fh.write(': 6, "score": 0.3}\n')
    assert [r["t0"] for r in f.new()] == [5]


def test_step_credits_chunk_and_logs(tmp_path):
    p = tmp_path / "scores.jsonl"
    p.write_text("")
    f, a, b = TL.Feed(p), TL.Attributor(3.0), bucket(0.9)
    for t in range(100, 112):
        a.note(float(t), "ig_reels")
    p.write_text(json.dumps({"t0": 100.0, "t1": 110.0, "score": 0.15}) + "\n")
    (r,) = TL.step(f, a, [b], 0.0, 0.3)
    assert r["bucket"] == "ig_reels" and r["drive"] == 0.5 and b.weight == 0.5


def test_store_keeps_user_weight(tmp_path):
    b = bucket(0.9)
    TL.apply(b, 0.3)
    C.save([b], tmp_path / "p.json")
    (got,) = C.load(tmp_path / "p.json")
    assert got.user_weight == 0.9 and got.weight == 0.3


def test_run_applies_tribe_score_midstream_and_later_stims_use_it(tmp_path):
    # Reason: the point of live TRIBE is that a chunk scored while you watch changes how hard the
    # *next* stimulus is; check that through the real CLI loop, not just the helpers.
    import argparse
    import io

    from gvs_pipeline.__main__ import _run
    from gvs_pipeline.flows import windows
    from gvs_pipeline.packets import to_line
    from test_reels_vs_dms import api_chatter, video

    def sliding(pk):
        return [o for w in windows(sorted(pk, key=lambda p: p.ts), 3.0, 1.0) for o in w]

    store = tmp_path / "p.json"
    C.save([C.enroll("ig_reels", 0.9, sliding(video(0, 30) + api_chatter(0, 30)))], store)
    feed = tmp_path / "scores.jsonl"
    feed.write_text("")
    (tmp_path / "n.json").write_text('{"score": 0.0}')
    (tmp_path / "h.json").write_text('{"score": 0.4}')
    pk = sorted(video(1000, 60) + api_chatter(1000, 60), key=lambda p: p.ts)
    lines = [to_line(p) for p in pk]

    def stream():
        for i, line in enumerate(lines):
            if i == len(lines) // 2:  # halfway through: TRIBE reports on seconds 1000-1010
                with feed.open("a") as fh:
                    fh.write(json.dumps({"t0": 1000.0, "t1": 1010.0, "score": 0.1}) + "\n")
            yield line

    a = argparse.Namespace(store=store, window=3.0, step=1.0, confirm=2, tribe_feed=feed,
                           tribe_anchors=[tmp_path / "n.json", tmp_path / "h.json"])
    out = io.StringIO()
    _run(stream(), a, out)
    recs = [json.loads(l) for l in out.getvalue().splitlines()]
    tribe = [r for r in recs if "tribe_chunk" in r]
    assert tribe and tribe[0]["bucket"] == "ig_reels" and tribe[0]["drive"] == 0.25 and tribe[0]["weight"] == 0.25
    i = recs.index(tribe[0])
    before = [r["intensity"] for r in recs[:i] if r.get("fired")]
    after = [r["intensity"] for r in recs[i:] if r.get("fired")]
    assert before and after and max(before) == 0.9 and max(after) == 0.25
