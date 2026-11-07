"""Sliding windows and the confirm/refractory trigger."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline.flows import Observation, windows
from gvs_pipeline.packets import Packet
from gvs_pipeline.trigger import CONFIRM, REFRACTORY_S, Trigger

from test_reels_vs_dms import CDN, CLIENT, api_chatter, photo_in_dm, texting, video

SAFETY_H = Path(__file__).resolve().parents[2] / "esp32" / "gvs_controller" / "safety.h"

times = st.lists(st.floats(0, 60, allow_nan=False), min_size=1, max_size=60).map(sorted)


def pk(ts):
    return [Packet(t, "8.8.8.8", CLIENT, 1000, sport=443, dport=50000) for t in ts]


@given(times)
def test_step_equal_to_window_is_tumbling(ts):
    # Reason: enrollment stores and old tests were built on tumbling windows; step=window must reproduce them.
    a = list(windows(pk(ts), 3.0))
    b = list(windows(pk(ts), 3.0, 3.0))
    assert a == b


@given(times, st.sampled_from([(3.0, 1.0), (4.0, 2.0), (3.0, 0.5)]))
def test_every_packet_counted_once_per_covering_window(ts, ws):
    # Reason: a window that drops or double-counts packets mis-states bytes, and the byte floor gates stimulation.
    window_s, step_s = ws
    got = {o.window_start: o.packets for w in windows(pk(ts), window_s, step_s) for o in w}
    want: dict[float, int] = {}
    for t in ts:
        k = int((t - window_s) // step_s) + 1
        while k * step_s <= t:
            want[k * step_s] = want.get(k * step_s, 0) + 1
            k += 1
    assert got == want


@given(times)
def test_windows_come_out_in_time_order(ts):
    starts = [w[0].window_start for w in windows(pk(ts), 3.0, 1.0)]
    assert starts == sorted(set(starts))


def test_long_gap_does_not_emit_empty_windows():
    out = list(windows(pk([0.0, 3600.0]), 3.0, 1.0))
    assert all(w for w in out) and len(out) == 6


def test_observations_carry_window_length():
    (w, *_) = windows(pk([0.0]), 3.0, 1.0)
    assert w[0].window_s == 3.0


def test_byte_floor_is_a_rate():
    # Reason: the 50 kB / 10 s floor applied unchanged to a 3 s window would ignore most short-video.
    assert C.min_bytes(3.0) / 3.0 == C.min_bytes(10.0) / 10.0


def test_classify_refuses_prototypes_from_other_window_length():
    # Reason: log-bytes, log-packets and burstiness scale with window length; a 10 s prototype vs a 3 s window is meaningless.
    b = C.enroll("x", 1.0, [Observation(0.0, "a.com", "", 10**6, 100, (0.5,) * 6, 10.0)])
    with pytest.raises(ValueError):
        C.classify(Observation(0.0, "a.com", "", 10**6, 100, (0.5,) * 6, 3.0), [b])


def test_enroll_records_window_length_and_store_keeps_it(tmp_path):
    b = C.enroll("x", 1.0, [Observation(0.0, "a.com", "", 10**6, 100, (0.5,) * 6, 3.0)])
    C.save([b], tmp_path / "p.json")
    assert C.load(tmp_path / "p.json")[0].window_s == 3.0


def test_refractory_matches_firmware_cooldown():
    # Reason: a shorter refractory sends stims the firmware refuses; a longer one silently drops pairings.
    ms = int(re.search(r"COOLDOWN_MS\s*=\s*(\d+)", SAFETY_H.read_text()).group(1))
    assert REFRACTORY_S * 1000 == ms


def d(bucket):
    o = Observation(0.0, "a.com", "", 10**6, 100, (0.5,) * 6, 3.0)
    return None if bucket is None else C.Decision(o, bucket, 1.0, 0.8, "domain")


def run(seq, step=1.0, **kw):
    t = Trigger(step, **kw)
    return [t.update(i * step, d(b)) is not None for i, b in enumerate(seq)]


def test_single_window_never_fires():
    # Reason: one odd window (a photo opened in a chat) must not be punished.
    assert run(["r", None, "r", None, "r"]) == [False] * 5


def test_fires_on_second_agreeing_step():
    assert run(["r", "r"]) == [False, True]


def test_disagreeing_buckets_reset_streak():
    assert run(["r", "s", "r", "s"]) == [False] * 4


def test_gap_in_steps_resets_streak():
    t = Trigger(1.0)
    assert t.update(0.0, d("r")) is None
    assert t.update(2.0, d("r")) is None
    assert t.update(3.0, d("r")) is not None


@given(st.lists(st.sampled_from(["r", "s", None]), max_size=200))
def test_fires_never_closer_than_refractory(seq):
    fired = [i for i, f in enumerate(run(seq)) if f]
    assert all(b - a >= REFRACTORY_S for a, b in zip(fired, fired[1:]))


@given(st.lists(st.sampled_from(["r", "s", None]), max_size=200))
def test_every_fire_ends_a_confirmed_run(seq):
    for i, f in enumerate(run(seq)):
        if f:
            assert i + 1 >= CONFIRM and len({seq[j] for j in range(i - CONFIRM + 1, i + 1)}) == 1 and seq[i] is not None


def sliding(pkts, w=3.0, s=1.0):
    return [o for win in windows(sorted(pkts, key=lambda p: p.ts), w, s) for o in win]


def buckets3():
    reels = C.enroll("ig_reels", 0.9, sliding(video(0, 30) + api_chatter(0, 30)))
    dms = C.enroll("ig_dms", 0.0, sliding(texting(0, 30) + photo_in_dm(5) + photo_in_dm(15) + photo_in_dm(25)))
    return [reels, dms]


def fires(pkts, bs):
    t = Trigger(1.0)
    out = []
    for win in windows(sorted(pkts, key=lambda p: p.ts), 3.0, 1.0):
        f = t.update(win[0].window_start, C.strongest(C.classify(o, bs) for o in win))
        if f is not None:
            out.append((win[0].window_start, f.bucket))
    return out


def test_reels_fire_within_four_seconds_at_3s_windows():
    # Reason: punishment loses effect with delay (research/conditioning.md); 10 s tumbling windows put it 5-20 s late.
    got = fires(video(100, 20) + api_chatter(100, 20), buckets3())
    assert got and got[0][1] == "ig_reels"
    first_close = got[0][0] + 3.0
    assert first_close - 100 <= 4.0


def test_dm_photo_never_fires_at_3s_windows():
    got = fires(texting(100, 20) + photo_in_dm(105) + photo_in_dm(112), buckets3())
    assert [b for _, b in got if b == "ig_reels"] == []
