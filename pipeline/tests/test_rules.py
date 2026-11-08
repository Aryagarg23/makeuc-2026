from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from hypothesis import given, settings, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline import dashboard as D
from gvs_pipeline import rules as R
from gvs_pipeline.__main__ import main
from gvs_pipeline.packets import to_line
from test_pipeline import chat_flow, flow, obs_of

W = 3.0


def tiktok_obs():
    return [o for o in obs_of(flow("9.9.9.9", "v.tiktokv.com", 0.0, 9), W) if o.service == "tiktokv.com"]


def tiktok_bucket(weight=0.9):
    return C.enroll("short_video", weight, obs_of(flow("9.9.9.9", "v.tiktokv.com", 0.0, 20), W))


def test_service_rule_fires_a_service_nobody_enrolled():
    # Reason: the dashboard's point is choosing what nauseates without recording an exemplar first.
    o = tiktok_obs()[0]
    assert C.classify(o, []).bucket is None
    d = R.Rules(services={"tiktokv.com": 0.7}).decide(o, [])
    assert (d.bucket, d.via, d.intensity) == ("rule:tiktokv.com", "rule", 0.7)


def test_never_rule_beats_an_enrolled_bucket():
    # Reason: "never" is the DMs case, so it must win over enrollment, not just add to it.
    o, b = tiktok_obs()[0], tiktok_bucket()
    assert R.Rules().decide(o, [b]).intensity == 0.9
    assert R.Rules(services={"tiktokv.com": 0}).decide(o, [b]).bucket is None


def test_bucket_switch_and_weight_override():
    o, b = tiktok_obs()[0], tiktok_bucket(0.9)
    assert R.Rules(buckets={"short_video": (True, 0.3)}).decide(o, [b]).intensity == 0.3
    assert R.Rules(buckets={"short_video": (False, 0.9)}).decide(o, [b]).bucket is None
    assert b.weight == 0.9  # the enrolled store is never mutated by a rule


def test_rule_keeps_the_rate_floor():
    # Reason: texting in a ruled app must not fire; the floor is what keeps background noise out.
    quiet = [o for o in obs_of(chat_flow("4.4.4.4", "web.whatsapp.net", 0.0, 9), W) if o.service == "whatsapp.net"]
    assert quiet and all(o.bytes < C.min_bytes(W) for o in quiet)
    assert all(R.Rules(services={"whatsapp.net": 1.0}).decide(o, []).bucket is None for o in quiet)


@settings(max_examples=60)
@given(st.floats(0, 1), st.floats(0, 1), st.booleans())
def test_rule_intensity_is_its_weight_and_never_above_one(ws, wb, on):
    o, b = tiktok_obs()[0], tiktok_bucket()
    d = R.Rules(services={"tiktokv.com": ws}, buckets={"short_video": (on, wb)}).decide(o, [b])
    assert 0.0 <= d.intensity <= 1.0
    assert d.intensity == (ws if ws > 0 else 0.0)  # a service rule always outranks the bucket


@pytest.mark.parametrize("raw", [
    {"services": {"tiktok.com": 1.5}}, {"services": {"tiktok.com": True}}, {"services": {"not a domain": 0.5}},
    {"buckets": {"ghost": {"on": True, "weight": 0.5}}}, {"paused": "yes"}, [],
])
def test_bad_rules_are_refused(raw):
    with pytest.raises(R.RuleError):
        R.Rules.parse(raw, known_buckets={"short_video"})


def _cli(tmp_path, capsys, rules: dict) -> list[dict]:
    ex = tmp_path / "tiktok.tsv"
    ex.write_text("\n".join(to_line(p) for p in flow("9.9.9.9", "v.tiktokv.com", 0.0, 20)) + "\n")
    store = tmp_path / "p.json"
    assert main(["--store", str(store), "--window", "3", "enroll", "short_video", str(ex), "--weight", "0.6"]) == 0
    (tmp_path / "rules.json").write_text(json.dumps(rules))
    cap = tmp_path / "cap.tsv"
    cap.write_text("\n".join(to_line(p) for p in flow("9.9.9.9", "v.tiktokv.com", 100.0, 12)) + "\n")
    capsys.readouterr()
    assert main(["--store", str(store), "--window", "3", "classify", str(cap)]) == 0
    return [json.loads(l) for l in capsys.readouterr().out.splitlines()]


def test_paused_decides_but_never_fires(tmp_path, capsys):
    live = _cli(tmp_path, capsys, {})
    assert any(r["fired"] for r in live)  # same traffic fires when not paused
    paused = _cli(tmp_path, capsys, {"paused": True})
    assert paused and not any(r["fired"] for r in paused)
    assert all(r.get("bucket") == "short_video" and r["paused"] for r in paused)


def test_rules_file_sits_next_to_the_store(tmp_path, capsys):
    recs = _cli(tmp_path, capsys, {"services": {"tiktokv.com": 0}})
    assert recs and not any(r.get("bucket") for r in recs)


def _req(url, body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **({"X-Dashboard-Key": key} if key else {})}
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_dashboard_api(tmp_path):
    b = tiktok_bucket()
    live = R.Live(tmp_path / "rules.json", {b.name})
    state = D.State(live, [b], armed=False, max_ma=None, window_s=W, step_s=1.0)
    srv = D.serve(state, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        o = tiktok_obs()[0]
        state.note(o.window_start, [R.Rules().decide(o, [b])], {"fired": True, "service": o.service,
                                                                 "bucket": b.name, "intensity": 0.9, "ms": 1850})
        code, page = _req(base + "/")
        assert code == 200 and b"Packet rules" in page
        s = json.loads(_req(base + "/api/state")[1])
        assert s["now"][0]["service"] == "tiktokv.com" and s["now"][0]["intensity"] == 0.9
        assert s["seen"][0]["service"] == "tiktokv.com" and s["stims"][0]["ms"] == 1850
        # Reason: the UNO Q's clock is months off (no internet), so ages must use the server's clock, not the browser's.
        assert 0 <= s["server_time"] - s["stims"][0]["wall"] < 5
        code, body = _req(base + "/api/rules", {"services": {"tiktokv.com": 0}, "buckets": {b.name: {"on": False, "weight": 0.4}}})
        assert code == 200 and json.loads(body)["rules"]["services"] == {"tiktokv.com": 0.0}
        on_disk = json.loads((tmp_path / "rules.json").read_text())
        code, body = _req(base + "/api/rules", {"services": {"tiktokv.com": 3}})
        assert code == 400 and "between 0 and 1" in json.loads(body)["error"]
        assert json.loads((tmp_path / "rules.json").read_text()) == on_disk  # a refused edit changes nothing
        assert live.get().decide(o, [b]).bucket is None  # and the accepted one is what the loop now reads
    finally:
        srv.shutdown()


def test_dashboard_off_loopback_needs_the_key(tmp_path):
    # Reason: on the UNO Q the page sits on the hotspot friends join for fun mode; they must not read your
    # traffic or change what nauseates you.
    assert D.key_for("127.0.0.1", tmp_path / "k") is None and not (tmp_path / "k").exists()
    key = D.key_for("0.0.0.0", tmp_path / "k")
    assert key and D.key_for("0.0.0.0", tmp_path / "k") == key  # stable, so the link keeps working
    b = tiktok_bucket()
    live = R.Live(tmp_path / "rules.json", {b.name})
    srv = D.serve(D.State(live, [b], False, None, W, 1.0), "127.0.0.1", 0, key)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert _req(base + "/")[0] == 200  # the page itself is harmless without the key
        assert _req(base + "/api/state")[0] == 401
        assert _req(base + "/api/state", key="wrong")[0] == 401
        assert _req(base + "/api/rules", {"paused": True})[0] == 401
        assert not (tmp_path / "rules.json").exists() and not live.get().paused
        assert _req(base + "/api/state", key=key)[0] == 200
        assert _req(base + "/api/rules", {"paused": True}, key=key)[0] == 200 and live.get().paused
    finally:
        srv.shutdown()
