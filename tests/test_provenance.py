from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.provenance import ProvenanceLedger


def stocked() -> ProvenanceLedger:
    ledger = ProvenanceLedger()
    ledger.register(0, "vendor-feed", "batch-77", "pipe-2.1")
    ledger.register(1, "vendor-feed", "batch-77", "pipe-2.1")
    ledger.register(2, "manual-upload", "batch-90", "pipe-2.1")
    ledger.transform(1, "price corrected", "ops-kiru")
    return ledger


class TestOrigins:
    def test_every_birth_is_recorded_once(self):
        ledger = stocked()
        with pytest.raises(Invalid, match="laundering"):
            ledger.register(0, "other", "b", "p")

    def test_anonymous_origins_are_refused(self):
        with pytest.raises(Invalid, match="anonymous origin"):
            ProvenanceLedger().register(9, "  ", "b", "p")


class TestChains:
    def test_the_chain_appends_and_never_edits(self):
        ledger = stocked()
        ledger.transform(1, "title retagged", "ops-ben")
        page = ledger.blame(1)
        assert "then price corrected by ops-kiru" in page
        assert "then title retagged by ops-ben" in page

    def test_anonymous_edits_birth_mysteries(self):
        with pytest.raises(Invalid, match="mystery documents"):
            stocked().transform(0, "  ", "ops")

    def test_transforming_the_unregistered_is_refused(self):
        with pytest.raises(Missing, match="no origin"):
            stocked().transform(99, "fix", "ops")


class TestBlame:
    def test_blame_reads_birth_and_chain(self):
        page = stocked().blame(1)
        assert page.startswith(
            "doc 1: born of vendor-feed/batch-77 via pipe-2.1"
        )

    def test_the_untouched_say_so(self):
        assert "untouched since birth" in stocked().blame(0)

    def test_the_unknown_have_no_provenance(self):
        with pytest.raises(Missing, match="no provenance"):
            stocked().blame(42)


class TestRecallAndFeeds:
    def test_a_suspect_batch_lists_its_deliveries(self):
        assert stocked().recall_list("batch-77") == [0, 1]

    def test_an_empty_batch_is_the_scarier_answer(self):
        with pytest.raises(Missing, match="scarier answer"):
            stocked().recall_list("batch-00")

    def test_the_feed_report_counts_corrections(self):
        page = stocked().feed_report()
        assert "vendor-feed: 2 document(s), 1 corrected (50%)" in page
        assert "manual-upload: 1 document(s), 0 corrected (0%)" in page
