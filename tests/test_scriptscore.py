from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.scriptscore import (
    FlagFactor,
    RecencyFactor,
    ScorePlan,
)


def storefront_plan() -> ScorePlan:
    return ScorePlan(
        factors=[
            RecencyFactor(
                name="fresh", field="published", half_life=30, cap=0.3
            ),
            FlagFactor(
                name="in-stock",
                field="stock",
                expected="yes",
                cap=0.2,
            ),
        ]
    )


class TestFactors:
    def test_recency_halves_on_schedule(self):
        factor = RecencyFactor(
            name="fresh", field="published", half_life=30, cap=0.3
        )
        now_value = factor.evaluate({"published": 100}, now=100)
        one_half_life = factor.evaluate({"published": 100}, now=130)
        assert now_value.value == 0.3
        assert one_half_life.value == 0.15

    def test_a_missing_field_contributes_zero_with_the_reason(self):
        factor = RecencyFactor(
            name="fresh", field="published", half_life=30, cap=0.3
        )
        value = factor.evaluate({}, now=100)
        assert value.value == 0.0
        assert value.detail == "no published"

    def test_flags_pay_the_cap_or_nothing(self):
        factor = FlagFactor(
            name="in-stock", field="stock", expected="yes", cap=0.2
        )
        assert factor.evaluate({"stock": "yes"}, now=0).value == 0.2
        assert factor.evaluate({"stock": "no"}, now=0).value == 0.0


class TestTheTiltBudget:
    def test_caps_past_the_budget_are_refused_at_build(self):
        with pytest.raises(Invalid, match="bury better matches"):
            ScorePlan(
                factors=[
                    FlagFactor(
                        name="a", field="x", expected=1, cap=0.3
                    ),
                    FlagFactor(
                        name="b", field="y", expected=1, cap=0.3
                    ),
                ]
            )

    def test_business_tilts_a_close_call(self):
        plan = storefront_plan()
        close_winner, _ = plan.score(
            0.98, {"published": 100, "stock": "yes"}, now=100
        )
        close_loser, _ = plan.score(1.0, {"stock": "no"}, now=100)
        assert close_winner > close_loser

    def test_business_cannot_bury_a_plainly_better_match(self):
        plan = storefront_plan()
        boosted, _ = plan.score(
            1.0, {"published": 100, "stock": "yes"}, now=100
        )
        plainly_better, _ = plan.score(2.0, {}, now=100)
        assert plainly_better > boosted

    def test_duplicate_factor_names_are_refused(self):
        with pytest.raises(Invalid, match="the table needs both"):
            ScorePlan(
                factors=[
                    FlagFactor(name="a", field="x", expected=1, cap=0.1),
                    FlagFactor(name="a", field="y", expected=1, cap=0.1),
                ]
            )

    def test_an_empty_plan_is_plain_relevance(self):
        with pytest.raises(Invalid, match="use that"):
            ScorePlan(factors=[])


class TestExplain:
    def test_the_table_shows_both_sides_of_the_argument(self):
        page = storefront_plan().explain(
            0.9, {"published": 70, "stock": "yes"}, now=100
        )
        lines = page.splitlines()
        assert lines[0] == "relevance 0.9"
        assert any(
            line.startswith("  + fresh: 0.15") for line in lines
        )
        assert "  + in-stock: 0.2 (stock='yes')" in lines
        assert lines[-1].startswith("= 1.25")
