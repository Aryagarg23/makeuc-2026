"""The UNO Q has no msgpack package; fun_server.py carries a minimal one. Check it against the real library."""
import msgpack
from hypothesis import given, strategies as st

import fun_server as F

scalars = st.none() | st.booleans() | st.integers(-2**40, 2**40) | st.text(max_size=40)
values = st.recursive(scalars, lambda c: st.lists(c, max_size=6), max_leaves=20)


@given(values)
def test_pack_matches_reference_decoder(v):
    assert msgpack.unpackb(F.mp_pack(v), raw=False) == v


@given(st.lists(scalars | st.floats(allow_nan=False), max_size=6) | st.dictionaries(st.text(max_size=8), scalars, max_size=5))
def test_unpack_reads_reference_encoder(v):
    got, end = F.mp_unpack(msgpack.packb(v, use_bin_type=True))
    assert got == v and end == len(msgpack.packb(v, use_bin_type=True))


def test_float_is_float32_for_the_sketch():
    # Reason: the sketch handlers take a 32-bit float; send exactly that type rather than rely on the router widening it.
    assert F.mp_pack(0.5)[0] == 0xCA
