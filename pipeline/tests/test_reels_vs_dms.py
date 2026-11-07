"""Reels vs DMs inside one app: both buckets share Instagram's domains, so shape decides."""
from __future__ import annotations

from hypothesis import given, strategies as st

from gvs_pipeline import classify as C
from gvs_pipeline.flows import N_FEATURES, Observation, windows
from gvs_pipeline.packets import Packet

CLIENT = "100.64.0.2"
CDN, API, MQTT = "31.13.1.1", "157.240.1.1", "157.240.2.2"


def hello(t, server, host):
    return Packet(t, CLIENT, server, 300, sport=50000, dport=443, sni=host)


def video(t0, seconds, pps=80):
    """Reels: sustained full-size packets from the CDN."""
    pk = [hello(t0, CDN, "scontent-cvg1-1.cdninstagram.com")]
    pk += [Packet(t0 + 0.01 + i / pps, CDN, CLIENT, 1400, sport=443, dport=50000) for i in range(seconds * pps)]
    return pk


def api_chatter(t0, seconds):
    pk = [hello(t0, API, "i.instagram.com")]
    for i in range(seconds * 3):
        a, b = (CLIENT, API) if i % 2 else (API, CLIENT)
        pk.append(Packet(t0 + 0.02 + i / 3, a, b, 400))
    return pk


def texting(t0, seconds):
    """DMs: small packets both ways on the API host and the MQTT push channel."""
    pk = [hello(t0, API, "i.instagram.com"), hello(t0, MQTT, "edge-mqtt.facebook.com")]
    for i in range(seconds * 4):
        a, b = (CLIENT, API) if i % 2 else (API, CLIENT)
        pk.append(Packet(t0 + 0.03 + i / 4, a, b, 150))
        pk.append(Packet(t0 + 0.04 + i / 4, MQTT, CLIENT, 90))
    return pk


def photo_in_dm(t0):
    """One image opened in a chat: a 1-second burst from the same CDN reels use."""
    pk = [hello(t0, CDN, "scontent-cvg1-1.cdninstagram.com")]
    pk += [Packet(t0 + 0.01 + i / 150, CDN, CLIENT, 1400, sport=443, dport=50000) for i in range(150)]
    return pk


def obs_of(pkts):
    return [o for w in windows(sorted(pkts, key=lambda p: p.ts), 10.0) for o in w]


def buckets(reels_w=0.9, dm_w=0.0):
    reels = C.enroll("ig_reels", reels_w, obs_of(video(0, 30) + api_chatter(0, 30)))
    dms = C.enroll("ig_dms", dm_w, obs_of(texting(0, 30) + photo_in_dm(5) + photo_in_dm(15) + photo_in_dm(25)))
    return [reels, dms]


def stim(pkts, bs):
    return [C.strongest(C.classify(o, bs) for o in w) for w in windows(sorted(pkts, key=lambda p: p.ts), 10.0)]


def test_cdn_is_shared_so_domain_alone_cannot_decide():
    reels, dms = buckets()
    assert "cdninstagram.com" in reels.domains & dms.domains


def test_reels_window_stimulates_as_reels():
    got = stim(video(1000, 20) + api_chatter(1000, 20), buckets())
    assert all(d is not None and d.bucket == "ig_reels" and d.via == "shared" and d.intensity > 0.5 for d in got)


def test_photo_in_dm_does_not_stimulate():
    # Reason: a photo in a chat loads from the reels CDN with >50 kB; only its burst shape separates it.
    bs = buckets()
    got = stim(texting(2000, 10) + photo_in_dm(2003), bs)
    assert got == [None]
    cdn_obs = [o for o in obs_of(texting(2000, 10) + photo_in_dm(2003)) if o.service == "cdninstagram.com"]
    assert [C.classify(o, bs).bucket for o in cdn_obs] in (["ig_dms"], [None])


def test_texting_never_stimulates():
    assert stim(texting(3000, 30), buckets()) == [None, None, None]


def test_shared_domain_not_decided_by_weight():
    # Reason: the first version picked the highest-weight bucket on a shared domain, so every
    # DM photo was punished as a reel. The weights here would make that bug fire.
    bs = buckets(reels_w=1.0, dm_w=0.0)
    for o in obs_of(photo_in_dm(4000)):
        if o.service == "cdninstagram.com":
            assert C.classify(o, bs).bucket != "ig_reels"


feature = st.floats(0, 1)
shape = st.tuples(*[feature] * N_FEATURES)


@given(shape, shape, shape)
def test_shared_decision_is_nearest_candidate_for_that_domain(x, a, b):
    ba = C.Bucket("a", 1.0, {"s.com"}, (0.5,) * N_FEATURES, {"s.com": a})
    bb = C.Bucket("b", 1.0, {"s.com"}, (0.5,) * N_FEATURES, {"s.com": b})
    d = C.classify(Observation(0.0, "s.com", "", 10**6, 100, x), [ba, bb])
    if d.bucket is not None:
        da, db = sum((p - q) ** 2 for p, q in zip(x, a)), sum((p - q) ** 2 for p, q in zip(x, b))
        assert (d.bucket == "a") == (da <= db)
        assert d.confidence >= C.SHARED_MARGIN


@given(shape)
def test_identical_candidates_never_decide(x):
    # Two buckets that look the same on a domain are indistinguishable there: no stimulus.
    s = {"s.com": (0.3,) * N_FEATURES}
    bs = [C.Bucket("a", 1.0, {"s.com"}, (0.3,) * N_FEATURES, s), C.Bucket("b", 1.0, {"s.com"}, (0.3,) * N_FEATURES, s)]
    assert C.classify(Observation(0.0, "s.com", "", 10**6, 100, x), bs).intensity == 0
