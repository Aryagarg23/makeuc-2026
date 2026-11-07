from __future__ import annotations

import io
import json

from hypothesis import given, settings, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline.__main__ import main
from gvs_pipeline.esp32_link import REARM_EVERY_S, Esp32
from gvs_pipeline.flows import UNKNOWN, Observation, features, service_of, unnamed_server, windows
from gvs_pipeline.packets import Packet, parse_line, to_line

CLIENT = "100.64.0.2"

ipv4 = st.tuples(*[st.integers(1, 254)] * 4).map(lambda t: ".".join(map(str, t)))
label = st.text("abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=10)
hostname = st.lists(label, min_size=2, max_size=4).map(".".join)


@st.composite
def packets(draw):
    v4a = draw(st.lists(ipv4, max_size=3))
    return Packet(
        ts=draw(st.floats(1e9, 2e9, allow_nan=False)),
        src=draw(ipv4),
        dst=draw(ipv4),
        length=draw(st.integers(40, 65535)),
        sport=draw(st.none() | st.integers(1, 65535)),
        dport=draw(st.none() | st.integers(1, 65535)),
        dns_name=draw(st.none() | hostname),
        dns_answers=tuple(v4a),
        sni=draw(st.none() | hostname),
        http_host=draw(st.none() | hostname),
    )


@given(packets())
def test_parse_inverts_to_line(p):
    assert parse_line(to_line(p)) == p


@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=200))
def test_parse_never_raises_on_garbage(line):
    parse_line(line)


@given(st.lists(label, min_size=2, max_size=5))
def test_service_is_suffix_of_host(labels):
    host = ".".join(labels)
    s = service_of(host)
    assert host.endswith(s) and 2 <= s.count(".") + 1 <= 3


def test_service_handles_multi_label_suffix():
    assert service_of("a.b.bbc.co.uk") == "bbc.co.uk"
    assert service_of("v16-webapp.tiktokv.com") == "tiktokv.com"


def flow(server, host, t0, seconds, pkt_len=1400, pps=50, sni=True):
    """A download-heavy flow: one SNI packet up, then server->client data."""
    out = []
    if sni:
        out.append(Packet(t0, CLIENT, server, 300, dport=443, sni=host))
    n = seconds * pps
    for i in range(n):
        out.append(Packet(t0 + 0.001 + i / pps, server, CLIENT, pkt_len, sport=443))
    return out


def chat_flow(server, host, t0, seconds, sni=True):
    """Small bidirectional packets, a few per second."""
    out = [Packet(t0, CLIENT, server, 300, dport=443, sni=host)] if sni else []
    for i in range(seconds * 4):
        a, b = (CLIENT, server) if i % 2 else (server, CLIENT)
        out.append(Packet(t0 + 0.01 + i / 4, a, b, 120))
    return out


def obs_of(pkts, window_s=10.0):
    return [o for w in windows(sorted(pkts, key=lambda p: p.ts), window_s) for o in w]


@given(st.permutations(list(range(30))))
def test_features_ignore_packet_order_within_window(perm):
    pk = flow("1.1.1.1", "x.example.com", 100.0, 3, pps=10, sni=False)
    shuffled = [pk[i] for i in perm]
    assert features(pk, {"1.1.1.1"}, 10.0) == features(shuffled, {"1.1.1.1"}, 10.0)


@given(st.lists(st.floats(0, 1), min_size=6, max_size=6))
def test_features_bounded(_):
    pk = flow("1.1.1.1", "x", 0.0, 5) + chat_flow("1.1.1.1", "x", 0.0, 5)
    assert all(0.0 <= f <= 1.0 for f in features(pk, {"1.1.1.1"}, 10.0))


def test_late_packets_attributed_via_sni_learned_earlier():
    pk = flow("9.9.9.9", "v.tiktokv.com", 0.0, 25)
    services = {o.service for o in obs_of(pk)}
    assert services == {"tiktokv.com"}


def test_named_flow_keeps_direction_feature():
    # Regression: named groups once computed down-fraction against server "" and always got 0.
    (o,) = obs_of(flow("9.9.9.9", "v.tiktokv.com", 0.0, 5))
    assert o.features[4] > 0.99


def test_dns_answers_name_flows_without_sni():
    dns = Packet(0.0, "100.100.100.100", CLIENT, 200, sport=53, dport=50000, dns_name="cdn.youtube.com", dns_answers=("8.8.4.4",))
    pk = [dns] + flow("8.8.4.4", "unused", 0.5, 5, sni=False)
    by_server = {(o.server or "named"): o.service for o in obs_of(pk)}
    # The DNS reply itself comes from an unnamed resolver; the data flow is named.
    assert by_server == {"100.100.100.100": UNKNOWN, "named": "youtube.com"}


@given(ipv4, ipv4, st.integers(1024, 65535))
def test_unnamed_download_keyed_by_remote_not_client(a, b, port):
    # Reason: keying unnamed flows by the client IP would merge every unnamed download into one blob.
    assert unnamed_server(Packet(0.0, a, CLIENT, 1400)) == a
    assert unnamed_server(Packet(0.0, CLIENT, b, 100, sport=port, dport=443)) == b
    assert unnamed_server(Packet(0.0, b, CLIENT, 1400, sport=443, dport=port)) == b


@given(st.floats(0, 1), st.floats(0, 1), st.sampled_from(["domain", "shape", "none"]))
def test_intensity_in_unit_interval(w, conf, via):
    assert 0.0 <= C.intensity(w, conf, via) <= 1.0


@given(st.floats(0, 1), st.floats(C.SHAPE_THRESHOLD, 1), st.floats(C.SHAPE_THRESHOLD, 1))
def test_shape_intensity_monotone_in_confidence(w, c1, c2):
    lo, hi = sorted((c1, c2))
    assert C.intensity(w, lo, "shape") <= C.intensity(w, hi, "shape")


@given(st.floats(0, 1))
def test_shape_intensity_zero_at_threshold(w):
    # Reason: a barely-matching unnamed flow must not get the same dose as a named domain hit.
    assert C.intensity(w, C.SHAPE_THRESHOLD, "shape") == 0.0


@given(st.floats(-5, 5, allow_nan=False))
def test_duration_within_firmware_ceiling(level):
    assert 500 <= C.duration_ms(level) <= 2000


def enrolled():
    video = C.enroll("short_video", 0.8, obs_of(flow("9.9.9.9", "v.tiktokv.com", 0.0, 30)))
    chat = C.enroll("chat", 0.3, obs_of(chat_flow("7.7.7.7", "web.whatsapp.com", 0.0, 30)))
    return [video, chat]


def test_one_shot_enroll_recalls_own_exemplar():
    buckets = enrolled()
    for b, pk in zip(buckets, [flow("9.9.9.9", "v.tiktokv.com", 0.0, 30), None]):
        if pk is None:
            continue
        ds = [C.classify(o, buckets) for o in obs_of(pk)]
        assert all(d.bucket == b.name and d.via == "domain" for d in ds)
    assert buckets[0].domains == {"tiktokv.com"}


def test_named_unenrolled_service_never_stimulated():
    # Reason: a named service we know and the user did not enroll is never shape-matched,
    # even if it looks exactly like an enrolled bucket (Netflix shaped like TikTok).
    buckets = enrolled()
    ds = [C.classify(o, buckets) for o in obs_of(flow("5.5.5.5", "nflxvideo.net", 0.0, 30))]
    assert ds and all(d.bucket is None and d.intensity == 0 for d in ds)


def test_unnamed_flow_falls_back_to_shape():
    # Reason: ECH/QUIC or mid-stream capture hides the name; shape is the only evidence left.
    buckets = enrolled()
    ds = [C.classify(o, buckets) for o in obs_of(flow("6.6.6.6", "", 0.0, 30, sni=False))]
    assert all(d.obs.service == UNKNOWN for d in ds)
    assert all(d.bucket == "short_video" and d.via == "shape" for d in ds)
    assert all(d.intensity < buckets[0].weight for d in ds)


@given(st.integers(1, C.MIN_BYTES - 1))
def test_small_windows_never_stimulated(nbytes):
    # Reason: a background keepalive to an enrolled domain is not exposure.
    buckets = enrolled()
    o = Observation(0.0, "tiktokv.com", "", nbytes, 1, buckets[0].shape)
    assert C.classify(o, buckets).intensity == 0


def test_strongest_picks_one_per_window_or_none():
    o = Observation(0.0, "a.com", "", 10**6, 10, (0.0,) * 6)
    ds = [C.Decision(o, "a", 1, 0.2, "domain"), C.Decision(o, "b", 1, 0.7, "domain")]
    assert C.strongest(ds).bucket == "b"
    assert C.strongest([C.Decision(o, None, 0, 0.0, "none")]) is None


def test_store_round_trip(tmp_path):
    b = enrolled()
    C.save(b, tmp_path / "p.json")
    got = C.load(tmp_path / "p.json")
    assert [(x.name, x.weight, x.domains, x.shape) for x in got] == [(x.name, x.weight, x.domains, x.shape) for x in b]


class FakeSerial:
    def __init__(self, replies=None):
        self.sent: list[dict] = []
        self.replies = list(replies or [])

    def write(self, data: bytes):
        self.sent.append(json.loads(data))
        return len(data)

    def readline(self) -> bytes:
        return (self.replies.pop(0) if self.replies else '{"ok":true}').encode() + b"\n"


@settings(max_examples=200)
@given(st.floats(allow_nan=False, allow_infinity=False, width=32), st.integers(0, 10**6))
def test_link_never_sends_intensity_outside_unit(level, ms):
    io_ = FakeSerial()
    Esp32(io_, clock=lambda: 0.0).stim("b", level, ms)
    stim = [m for m in io_.sent if m["cmd"] == "stim"][0]
    assert 0.0 <= stim["intensity"] <= 1.0


def test_link_rearms_before_firmware_expiry():
    # Reason: firmware disarms after 600 s; re-arming at 300 s keeps a live session armed.
    t = [0.0]
    io_ = FakeSerial()
    esp = Esp32(io_, clock=lambda: t[0])
    esp.stim("b", 0.5, 500)
    t[0] = REARM_EVERY_S - 1
    esp.stim("b", 0.5, 500)
    t[0] = REARM_EVERY_S + 1
    esp.stim("b", 0.5, 500)
    assert [m["cmd"] for m in io_.sent] == ["arm", "stim", "stim", "arm", "stim"]


def test_cli_enroll_then_classify(tmp_path, capsys):
    ex = tmp_path / "tiktok.tsv"
    ex.write_text("\n".join(to_line(p) for p in flow("9.9.9.9", "v.tiktokv.com", 0.0, 20)) + "\n")
    store = tmp_path / "p.json"
    assert main(["--store", str(store), "enroll", "short_video", str(ex), "--weight", "0.6"]) == 0
    capsys.readouterr()
    mixed = sorted(
        flow("9.9.9.9", "v.tiktokv.com", 100.0, 10) + chat_flow("4.4.4.4", "mail.google.com", 100.0, 10),
        key=lambda p: p.ts,
    )
    cap = tmp_path / "mixed.tsv"
    cap.write_text("\n".join(to_line(p) for p in mixed) + "\n")
    assert main(["--store", str(store), "classify", str(cap)]) == 0
    recs = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert recs and all(r["bucket"] == "short_video" and r["intensity"] == 0.6 for r in recs)


@given(st.sampled_from(["estop", "not_armed"]))
def test_link_never_rearms_after_external_stop(reason):
    # Reason: E-stop or a manual disarm is the person opting out; auto re-arm would undo it.
    t = [0.0]
    io_ = FakeSerial(['{"ok":true}', '{"ok":false,"reason":"%s"}' % reason])
    esp = Esp32(io_, clock=lambda: t[0])
    esp.stim("b", 0.5, 500)
    t[0] = REARM_EVERY_S * 10
    r = esp.stim("b", 0.5, 500)
    assert r == {"ok": False, "reason": "halted", "cause": reason}
    assert [m["cmd"] for m in io_.sent] == ["arm", "stim"]


def test_link_cooldown_does_not_halt():
    io_ = FakeSerial(['{"ok":true}', '{"ok":false,"reason":"cooldown"}'])
    esp = Esp32(io_, clock=lambda: 0.0)
    esp.stim("b", 0.5, 500)
    esp.stim("b", 0.5, 500)
    assert esp.halted is None


def test_link_halts_when_arm_refused():
    io_ = FakeSerial(['{"ok":false,"reason":"estop"}'])
    esp = Esp32(io_, clock=lambda: 0.0)
    assert esp.stim("b", 0.5, 500)["ok"] is False
    assert esp.halted == "estop" and [m["cmd"] for m in io_.sent] == ["arm"]
