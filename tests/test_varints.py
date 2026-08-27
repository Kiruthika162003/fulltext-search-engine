from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.varints import (
    decode_postings,
    decode_varint,
    encode_postings,
    encode_varint,
    savings_report,
)


class TestVarints:
    def test_small_numbers_take_one_byte(self):
        assert len(encode_varint(0)) == 1
        assert len(encode_varint(127)) == 1

    def test_the_boundary_crosses_at_128(self):
        assert len(encode_varint(128)) == 2
        assert len(encode_varint(16383)) == 2
        assert len(encode_varint(16384)) == 3

    def test_round_trips_hold(self):
        for value in (0, 1, 127, 128, 300, 16384, 10**9):
            encoded = encode_varint(value)
            decoded, consumed = decode_varint(encoded, 0)
            assert decoded == value
            assert consumed == len(encoded)

    def test_debt_is_refused(self):
        with pytest.raises(Invalid, match="never debt"):
            encode_varint(-1)

    def test_a_truncated_stream_refuses_to_guess(self):
        truncated = encode_varint(300)[:1]
        with pytest.raises(Invalid, match="invent a document"):
            decode_varint(truncated, 0)


class TestPostings:
    def test_every_troublesome_shape_round_trips(self):
        for shape in (
            [0],
            [7],
            [0, 1, 2, 3],
            [5, 200, 20000, 20001],
            list(range(50)),
        ):
            assert decode_postings(encode_postings(shape)) == shape

    def test_dense_runs_pack_to_a_byte_per_doc(self):
        packed = encode_postings(list(range(100)))
        assert len(packed) == 100

    def test_descending_ids_are_phantom_duplicates(self):
        with pytest.raises(Invalid, match="phantom"):
            encode_postings([5, 5])
        with pytest.raises(Invalid, match="phantom"):
            encode_postings([9, 3])

    def test_empty_lists_encode_nothing(self):
        with pytest.raises(Invalid, match="encodes nothing"):
            encode_postings([])


class TestSavings:
    def test_the_report_measures_this_list(self):
        page = savings_report(list(range(100)))
        assert page.startswith(
            "100 posting(s): 800 flat bytes -> 100 packed (8.0x)"
        )
        assert "not quoted from the paper" in page
