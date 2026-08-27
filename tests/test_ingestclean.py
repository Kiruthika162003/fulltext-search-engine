from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.ingestclean import CleanLedger, is_idempotent


class TestStages:
    def test_markup_dies_but_its_words_survive(self):
        ledger = CleanLedger()
        assert ledger.clean("<p>copper <b>kettle</b></p>") == (
            "copper kettle"
        )

    def test_control_characters_vanish(self):
        ledger = CleanLedger()
        assert ledger.clean("cop\x00per\x07 kettle") == (
            "copper kettle"
        )

    def test_soft_hyphens_stop_splitting_words(self):
        ledger = CleanLedger()
        assert ledger.clean("ket­tle") == "kettle"

    def test_zero_width_characters_vanish(self):
        ledger = CleanLedger()
        assert ledger.clean("ket\u200btle") == "kettle"

    def test_whitespace_collapses_last(self):
        ledger = CleanLedger()
        assert ledger.clean("  copper\t\n kettle  ") == (
            "copper kettle"
        )

    def test_holes_in_the_feed_are_named(self):
        with pytest.raises(Invalid, match="sent a hole"):
            CleanLedger().clean(None)


class TestIdempotence:
    def test_clean_of_clean_is_clean(self):
        ledger = CleanLedger()
        assert is_idempotent(
            ledger, "<div>ket­tle   on\x07 the stove</div>"
        )

    def test_plain_text_passes_untouched(self):
        ledger = CleanLedger()
        assert ledger.clean("copper kettle") == "copper kettle"
        assert ledger.counts == {}


class TestTheLedger:
    def test_each_stage_counts_what_it_touched(self):
        ledger = CleanLedger()
        ledger.clean("<p>one</p>")
        ledger.clean("two\x00")
        ledger.clean("plain three")
        page = ledger.report()
        assert "3 document(s) cleaned" in page
        assert "markup: touched 1 (33%)" in page
        assert "control: touched 1 (33%)" in page

    def test_a_markup_flood_points_at_the_exporter(self):
        ledger = CleanLedger()
        ledger.clean("<p>one</p>")
        ledger.clean("<p>two</p>")
        ledger.clean("three")
        assert "go look at it" in ledger.report()

    def test_an_idle_ledger_says_so(self):
        assert CleanLedger().report() == "nothing cleaned yet"
