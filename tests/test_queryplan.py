from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.queryplan import explain, plan_intersection
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def catalog() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    for number in range(20):
        parts = ["common"]
        if number < 10:
            parts.append("medium")
        if number < 2:
            parts.append("rare")
        builder.add({"body": " ".join(parts)})
    return builder.seal("catalog")


class TestOrdering:
    def test_the_rarest_term_leads(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "medium", "rare"]
        )
        assert [step.term for step in plan.steps] == [
            "rare",
            "medium",
            "common",
        ]

    def test_the_candidate_bound_only_shrinks(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "medium", "rare"]
        )
        bounds = [step.candidate_bound for step in plan.steps]
        assert bounds == sorted(bounds, reverse=True)
        assert bounds == [2, 2, 2]

    def test_the_chosen_ceiling_never_exceeds_the_written_order(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "medium", "rare"]
        )
        assert plan.cost_ceiling <= plan.naive_ceiling
        assert plan.saved() == plan.naive_ceiling - plan.cost_ceiling

    def test_a_missing_term_plans_to_zero(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "zebra"]
        )
        assert plan.steps[0].term == "zebra"
        assert plan.steps[0].list_length == 0

    def test_planning_nothing_is_refused(self):
        with pytest.raises(Invalid):
            plan_intersection(catalog(), "body", [])


class TestExplain:
    def test_the_explanation_shows_each_step_and_the_ceilings(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "medium", "rare"]
        )
        page = explain(plan)
        assert "1. rare (list 2, candidates bounded at 2)" in page
        assert "ceilings, not invoices" in page

    def test_an_empty_rarest_term_calls_the_rest_theatre(self):
        plan = plan_intersection(catalog(), "body", ["common", "zebra"])
        assert "everything after step 1 is theatre" in explain(plan)

    def test_the_numbers_are_the_known_arithmetic(self):
        plan = plan_intersection(
            catalog(), "body", ["common", "medium", "rare"]
        )
        assert plan.cost_ceiling == (2 + 10) + (2 + 20)
        assert plan.naive_ceiling == (20 + 10) + (10 + 2)
