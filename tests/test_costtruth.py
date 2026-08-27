from __future__ import annotations

from quarry.evals import costtruth
from quarry.evals.registry import EVALS


class TestCostTruth:
    def test_the_grade_holds(self):
        assert costtruth.run().holds

    def test_single_terms_and_unions_are_exact(self):
        numbers = costtruth.run().numbers
        assert numbers["est_market"] == numbers["true_market"] == 3
        assert (
            numbers["est_market_OR_rain"]
            == numbers["true_market_OR_rain"]
            == 6
        )

    def test_the_intersection_divergence_is_pinned(self):
        numbers = costtruth.run().numbers
        assert numbers["est_+market_+square"] == 2
        assert numbers["true_+market_+square"] == 5
        assert numbers["worst_ratio"] == 2.5

    def test_the_sentence_names_the_engine_fact(self):
        grade = costtruth.run()
        assert "merges instead of galloping" in grade.sentence

    def test_the_eval_is_registered(self):
        assert "quarry.evals.costtruth" in EVALS
