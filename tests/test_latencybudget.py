from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.latencybudget import LatencyBudget, even_budget


def standard() -> LatencyBudget:
    return LatencyBudget(
        slices={
            "parse": 5,
            "retrieve": 40,
            "score": 30,
            "rerank": 15,
            "render": 10,
        }
    )


class TestConstruction:
    def test_every_stage_needs_a_slice(self):
        with pytest.raises(Invalid, match="no slice"):
            LatencyBudget(slices={"parse": 5})

    def test_unknown_stages_are_named(self):
        with pytest.raises(Invalid, match="unknown stage"):
            LatencyBudget(
                slices={
                    "parse": 5,
                    "retrieve": 40,
                    "score": 30,
                    "rerank": 15,
                    "render": 10,
                    "teleport": 1,
                }
            )

    def test_the_even_split_gives_the_remainder_to_render(self):
        budget = even_budget(103)
        assert budget.slices["parse"] == 20
        assert budget.slices["render"] == 23
        assert budget.total_budget() == 103


class TestSpending:
    def test_early_finishers_donate_forward(self):
        budget = standard()
        assert "3ms spare" in budget.charge("parse", 2)
        message = budget.charge("retrieve", 42)
        assert "covered by the donation pool" in message
        assert not budget.breached()

    def test_the_pool_runs_dry_honestly(self):
        budget = standard()
        budget.charge("parse", 5)
        budget.charge("retrieve", 40)
        budget.charge("score", 30)
        message = budget.charge("rerank", 40)
        assert "pool is dry" in message
        assert budget.breached()

    def test_stages_spend_in_pipeline_order(self):
        budget = standard()
        with pytest.raises(Invalid, match="pipeline order"):
            budget.charge("score", 10)

    def test_negative_time_is_a_clock_bug(self):
        with pytest.raises(Invalid, match="clock bug"):
            standard().charge("parse", -1)


class TestTheReport:
    def test_each_stage_states_slice_spend_and_verdict(self):
        budget = standard()
        budget.charge("parse", 2)
        budget.charge("retrieve", 42)
        page = budget.report()
        assert "parse: 2ms of 5ms (on time)" in page
        assert "retrieve: 42ms of 40ms (over by 2ms)" in page
        assert page.endswith("total 44ms of 100ms: inside the deadline")

    def test_a_dry_pool_is_a_breached_deadline(self):
        budget = standard()
        budget.charge("parse", 5)
        budget.charge("retrieve", 60)
        assert "DEADLINE BREACHED" in budget.report()
