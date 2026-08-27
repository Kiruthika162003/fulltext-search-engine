from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.resultdiff import SuiteDiff, diff_query


class TestOneQuery:
    def test_identical_rankings_are_stable(self):
        held = diff_query("q", [1, 2, 3], [1, 2, 3])
        assert held.stable()
        assert held.disorder == 0.0
        assert held.summary() == "'q': unchanged"

    def test_entries_exits_and_moves_are_all_named(self):
        held = diff_query("q", [1, 2, 3], [2, 1, 4])
        lines = sorted(move.line() for move in held.moves)
        assert "doc 1: down from 0 to 1" in lines
        assert "doc 2: up from 1 to 0" in lines
        assert "doc 3: exited from 2" in lines
        assert "doc 4: entered at 2" in lines

    def test_a_full_reversal_scores_disorder_one(self):
        held = diff_query("q", [1, 2, 3, 4], [4, 3, 2, 1])
        assert held.disorder == 1.0

    def test_a_swap_scores_between(self):
        held = diff_query("q", [1, 2, 3, 4], [2, 1, 3, 4])
        assert 0.0 < held.disorder < 1.0

    def test_repeated_documents_are_refused(self):
        with pytest.raises(Invalid, match="bless the breakage"):
            diff_query("q", [1, 1, 2], [1, 2, 3])

    def test_the_summary_counts_each_kind(self):
        held = diff_query("q", [1, 2, 3], [2, 1, 4])
        assert held.summary() == (
            "'q': 1 entered, 1 exited, 2 moved, disorder 1.0"
        )


class TestTheSuite:
    def suite(self) -> SuiteDiff:
        return SuiteDiff(
            diffs=(
                diff_query("calm", [1, 2], [1, 2]),
                diff_query("swap", [1, 2], [2, 1]),
                diff_query("gone", [7, 8], []),
                diff_query("fresh", [], [9]),
            )
        )

    def test_churn_is_the_changed_share(self):
        assert self.suite().churn() == 0.75

    def test_the_noisiest_lead_the_report(self):
        noisy = self.suite().noisiest(top_n=2)
        assert noisy[0].canonical == "swap"

    def test_vanished_queries_are_shouted(self):
        assert self.suite().emptied() == ["gone"]
        assert "'gone': RESULTS VANISHED" in self.suite().report()

    def test_an_empty_suite_is_refused(self):
        with pytest.raises(Invalid, match="no churn"):
            SuiteDiff(diffs=()).churn()

    def test_the_report_leads_with_churn(self):
        assert self.suite().report().startswith(
            "churn: 75% of 4 queries changed"
        )
