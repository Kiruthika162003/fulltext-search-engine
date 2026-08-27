from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.mergebudget import (
    MergeCandidate,
    plan_merges,
    plan_report,
)


def tidy_two() -> MergeCandidate:
    return MergeCandidate(
        name="tidy-two", live_docs=100, tombstones=40, segments_in=2
    )


def wide_four() -> MergeCandidate:
    return MergeCandidate(
        name="wide-four", live_docs=400, tombstones=10, segments_in=4
    )


def giant() -> MergeCandidate:
    return MergeCandidate(
        name="giant", live_docs=5000, tombstones=200, segments_in=2
    )


class TestCandidates:
    def test_single_segment_merges_merge_nothing(self):
        with pytest.raises(Invalid, match="merges nothing"):
            MergeCandidate(
                name="lonely",
                live_docs=10,
                tombstones=0,
                segments_in=1,
            )

    def test_value_is_benefit_per_document_rewritten(self):
        held = tidy_two()
        assert held.benefit() == 50
        assert held.cost() == 100
        assert held.value() == 0.5


class TestPlanning:
    def test_the_best_value_spends_first(self):
        decisions = plan_merges([wide_four(), tidy_two()], 450)
        assert decisions[0].candidate.name == "tidy-two"
        assert decisions[0].admitted

    def test_the_budget_is_a_real_fence(self):
        decisions = plan_merges([wide_four(), tidy_two()], 450)
        wide = next(
            held
            for held in decisions
            if held.candidate.name == "wide-four"
        )
        assert not wide.admitted
        assert "only 350 left" in wide.reason

    def test_oversized_merges_queue_for_the_quiet_window(self):
        decisions = plan_merges([giant()], 1000)
        assert not decisions[0].admitted
        assert "quiet window" in decisions[0].reason

    def test_zero_budgets_must_be_typed_deliberately(self):
        with pytest.raises(Invalid, match="skip"):
            plan_merges([tidy_two()], 0)

    def test_no_candidates_is_an_empty_plan(self):
        assert plan_merges([], 100) == []


class TestTheReport:
    def test_the_report_totals_the_rewrite_bill(self):
        page = plan_report(plan_merges([wide_four(), tidy_two()], 600))
        assert "RUN tidy-two" in page
        assert "RUN wide-four" in page
        assert page.endswith("2 of 2 admitted, 500 documents to rewrite")

    def test_an_empty_plan_says_so(self):
        assert "nobody looked" in plan_report([])
