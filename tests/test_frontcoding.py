from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.frontcoding import (
    decode_dictionary,
    encode_dictionary,
    lookup,
    savings_report,
)

TERMS = [
    "search",
    "searched",
    "searcher",
    "searching",
    "seat",
    "settle",
    "settled",
    "stone",
    "stove",
]


class TestCoding:
    def test_the_round_trip_is_exact(self):
        blocks = encode_dictionary(TERMS)
        assert decode_dictionary(blocks) == TERMS

    def test_blocks_start_with_full_terms(self):
        blocks = encode_dictionary(TERMS)
        assert blocks[0].lead == "search"
        assert blocks[1].lead == "seat"
        assert blocks[2].lead == "stove"

    def test_shared_fronts_are_not_stored_twice(self):
        blocks = encode_dictionary(TERMS)
        shared, suffix = blocks[0].tails[0]
        assert (shared, suffix) == (6, "ed")

    def test_unsorted_input_stores_clean_garbage(self):
        with pytest.raises(Invalid, match="worst kind"):
            encode_dictionary(["stove", "search"])
        with pytest.raises(Invalid, match="worst kind"):
            encode_dictionary(["seat", "seat"])

    def test_an_empty_dictionary_codes_nothing(self):
        with pytest.raises(Invalid, match="codes nothing"):
            encode_dictionary([])


class TestLookup:
    def test_present_terms_are_found(self):
        blocks = encode_dictionary(TERMS)
        assert all(lookup(blocks, term) for term in TERMS)

    def test_absent_terms_are_absent(self):
        blocks = encode_dictionary(TERMS)
        assert not lookup(blocks, "sea")
        assert not lookup(blocks, "stoves")
        assert not lookup(blocks, "aardvark")

    def test_prefix_arithmetic_alone_is_never_trusted(self):
        blocks = encode_dictionary(TERMS)
        assert not lookup(blocks, "searchers")


class TestSavings:
    def test_the_report_counts_the_leads(self):
        page = savings_report(TERMS)
        assert page.startswith("9 term(s) in 3 block(s) of 4:")
        assert "not waved away" in page

    def test_kindred_terms_compress_well(self):
        page = savings_report(TERMS)
        raw = int(page.split(": ")[1].split(" raw")[0])
        stored = int(page.split("-> ")[1].split(" stored")[0])
        assert stored < raw
