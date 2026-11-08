"""HTTP link to the XIAO GVS firmware."""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from gvs_pipeline import gvs_link as L
from gvs_pipeline.__main__ import main
from gvs_pipeline.gvs_link import Gvs, whole_cycles_ms

INO = (Path(__file__).resolve().parents[2] / "gvs" / "firmware" / "gvs_controller" / "gvs_controller.ino").read_text()


def fw(name, cast=float):
    return cast(re.search(rf"\b{name}\s*=\s*([\d.]+)", INO).group(1))


class FakeHttp:
    def __init__(self, replies=None):
        self.calls: list[tuple[str, dict]] = []
        self.replies = list(replies or [])

    def __call__(self, url):
        u = urllib.parse.urlsplit(url)
        self.calls.append((u.path, dict(urllib.parse.parse_qsl(u.query))))
        return self.replies.pop(0) if self.replies else (200, "ok\n")


def link(replies=None, max_ma=1.0, hz=1.0):
    h = FakeHttp(replies)
    return Gvs("http://dev", "tok", max_ma, hz, get=h), h


def test_link_constants_match_firmware():
    # Reason: the link clamps to these; if the firmware changes and the link doesn't, requests get silently re-clamped.
    assert (L.FW_MAX_MA, L.FW_MAX_MS, L.FW_MIN_MS) == (fw("FW_MAX_MA"), fw("MAX_MS", int), 2 * fw("RAMP_MS", int))


@given(st.floats(allow_nan=False, allow_infinity=False), st.integers(0, 10**6),
       st.floats(0.05, 2.0), st.sampled_from([0.5, 0.8, 1.0, 1.25, 2.0]))
def test_pulse_is_always_bounded_sine_of_whole_cycles(level, ms, max_ma, hz):
    # Reason: whole cycles of a zero-mean sine leave no net charge on the skin (research/gvs.md §7 F2); DC never.
    g, h = link(max_ma=max_ma, hz=hz)
    g.stim("b", level, ms)
    path, q = h.calls[0]
    assert path == "/pulse" and q["mode"] == "sine" and q["token"] == "tok"
    assert 0.0 <= float(q["ma"]) <= max_ma <= L.FW_MAX_MA
    dur = int(q["ms"])
    assert L.FW_MIN_MS <= dur <= L.FW_MAX_MS
    cycles = dur * hz / 1000
    assert abs(cycles - round(cycles)) < 1e-6 and round(cycles) >= 1


def test_duration_rounds_to_nearest_cycle():
    assert whole_cycles_ms(2000, 1.0) == 2000 and whole_cycles_ms(500, 1.0) == 1000 and whole_cycles_ms(1700, 2.0) == 1500


@pytest.mark.parametrize("hz", [1.5, 3.0, 0.25])
def test_hz_without_whole_ms_period_or_out_of_range_refused(hz):
    # Reason: 1.5 Hz has a 666.67 ms period; integer-ms durations can't hold whole cycles, so charge wouldn't balance.
    with pytest.raises(ValueError):
        Gvs("http://dev", "t", 1.0, hz)


@pytest.mark.parametrize("max_ma", [0.0, -1.0, 2.01])
def test_max_ma_outside_firmware_range_refused(max_ma):
    with pytest.raises(ValueError):
        Gvs("http://dev", "t", max_ma)


@given(st.sampled_from([403, 423]))
def test_link_never_sends_again_after_fault_or_bad_token(code):
    # Reason: a latched fault or a rejected token means a person or the device stopped this; retrying would override them.
    g, h = link([(code, "x")])
    g.stim("b", 0.5, 1000)
    r = g.stim("b", 0.5, 1000)
    assert r["reason"] == "halted" and len(h.calls) == 1


@given(st.sampled_from([409, 429]))
def test_busy_and_cooldown_are_skips_not_halts(code):
    g, h = link([(code, "x")])
    assert g.stim("b", 0.5, 1000)["ok"] is False
    assert g.halted is None and g.stim("b", 0.5, 1000)["ok"] is True


def test_unreachable_is_a_skip():
    def boom(url):
        raise OSError("no route")
    g = Gvs("http://dev", "t", 1.0, get=boom)
    assert g.stim("b", 0.5, 1000)["reason"] == "unreachable" and g.halted is None


def test_polarity_alternates_only_on_delivered_pulses():
    g, h = link([(200, "ok"), (429, "cooldown"), (200, "ok")])
    for _ in range(3):
        g.stim("b", 0.5, 1000)
    assert [q["pol"] for _, q in h.calls] == ["0", "1", "1"]


def test_live_with_device_requires_max_ma(tmp_path, monkeypatch):
    # Reason: there is no safe default current; it has to be the ceiling the wearer titrated to.
    env = tmp_path / "device.env"
    env.write_text("GVS_URL=http://dev\nGVS_TOKEN=t\n")
    monkeypatch.setattr("sys.stdin", iter([]))
    with pytest.raises(SystemExit):
        main(["--store", str(tmp_path / "p.json"), "live", "--gvs", str(env)])


def test_env_file_parsing(tmp_path):
    p = tmp_path / "d.env"
    p.write_text("# c\nGVS_URL=http://192.168.4.1\nGVS_TOKEN=abc\n")
    g = Gvs.from_env(p, 0.5)
    assert g.base == "http://192.168.4.1" and g.token == "abc"


def test_hourly_limit_reported_as_such_and_not_a_halt():
    g, _ = link([(429, "hourly_limit\n")])
    r = g.stim("b", 0.5, 1000)
    assert r["reason"] == "hourly_limit" and g.halted is None
