from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.suggestguard import SuggestGuard

TODAY = 1000


class TestBlocking:
    def test_blocks_survive_casing_tricks(self):
        guard = SuggestGuard()
        guard.block("Slur", who="trust-team")
        assert not guard.admit("SLUR", 100, TODAY - 1, TODAY)
        assert guard.rejections["blocklist"] == 1

    def test_blocking_nothing_blocks_nothing(self):
        with pytest.raises(Invalid, match="blocks nothing"):
            SuggestGuard().block("the", who="trust-team")


class TestAdmission:
    def test_healthy_terms_are_admitted(self):
        guard = SuggestGuard()
        assert guard.admit("kettle", 10, TODAY - 5, TODAY)

    def test_thin_evidence_rides_typos(self):
        guard = SuggestGuard()
        assert not guard.admit("ketle", 2, TODAY - 1, TODAY)
        assert guard.rejections["thin-evidence"] == 1

    def test_stale_terms_are_archaeology(self):
        guard = SuggestGuard()
        assert not guard.admit("discman", 500, TODAY - 200, TODAY)
        assert guard.rejections["stale"] == 1

    def test_future_sightings_expose_broken_clocks(self):
        with pytest.raises(Invalid, match="future"):
            SuggestGuard().admit("kettle", 10, TODAY + 3, TODAY)


class TestExplain:
    def test_every_status_is_a_lookup_not_an_investigation(self):
        guard = SuggestGuard()
        guard.block("slur", who="trust-team")
        assert "never surfaces" in guard.explain(
            "slur", 100, TODAY - 1, TODAY
        )
        assert "needs 3" in guard.explain(
            "ketle", 1, TODAY - 1, TODAY
        )
        assert "archaeology" in guard.explain(
            "discman", 500, TODAY - 200, TODAY
        )
        assert guard.explain(
            "kettle", 10, TODAY - 5, TODAY
        ).endswith("admitted")


class TestFiltering:
    def test_the_filter_returns_analyzed_survivors(self):
        guard = SuggestGuard()
        guard.block("slur", who="trust-team")
        survivors = guard.filter_candidates(
            [
                ("Kettles", 10, TODAY - 5),
                ("slur", 90, TODAY - 5),
                ("ketle", 1, TODAY - 5),
                ("teapot", 8, TODAY - 80),
            ],
            TODAY,
        )
        assert survivors == ["kettl", "teapot"]

    def test_the_ledger_counts_by_reason(self):
        guard = SuggestGuard()
        guard.block("slur", who="trust-team")
        guard.filter_candidates(
            [
                ("slur", 90, TODAY - 5),
                ("ketle", 1, TODAY - 5),
                ("discman", 500, TODAY - 200),
            ],
            TODAY,
        )
        page = guard.rejection_ledger()
        assert "blocklist: 1" in page
        assert "thin-evidence: 1" in page
        assert "stale: 1" in page
