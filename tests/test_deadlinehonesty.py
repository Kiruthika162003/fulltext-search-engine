from __future__ import annotations

from quarry.evals import deadlinehonesty
from quarry.evals.registry import EVALS


class TestDeadlineHonesty:
    def test_the_grade_holds(self):
        assert deadlinehonesty.run().holds

    def test_partial_loses_recall_never_correctness(self):
        numbers = deadlinehonesty.run().numbers
        assert numbers["full_recall"] == 1.0
        assert numbers["tight_recall"] == 0.8
        assert numbers["tight_precision"] == 1.0

    def test_the_loss_is_stated_in_documents(self):
        numbers = deadlinehonesty.run().numbers
        assert numbers["docs_unreached"] == 3

    def test_partials_are_counted_not_shrugged(self):
        numbers = deadlinehonesty.run().numbers
        assert numbers["partial_share"] == 0.5

    def test_the_eval_is_registered(self):
        assert "quarry.evals.deadlinehonesty" in EVALS
