from __future__ import annotations

from quarry.evals import foldgain
from quarry.evals.registry import EVALS


class TestFoldgain:
    def test_the_grade_holds(self):
        grade = foldgain.run()
        assert grade.holds

    def test_both_sides_reaches_everything(self):
        numbers = foldgain.run().numbers
        assert numbers["plain_recall"] == 0.5
        assert numbers["folded_recall"] == 1.0
        assert numbers["folded_precision"] == 1.0

    def test_one_sided_folding_is_worse_than_none(self):
        numbers = foldgain.run().numbers
        assert numbers["one_sided_recall"] == 0.0
        assert (
            numbers["one_sided_recall"] < numbers["plain_recall"]
        )

    def test_the_eval_is_registered(self):
        assert "quarry.evals.foldgain" in EVALS

    def test_the_sentence_names_both_findings(self):
        grade = foldgain.run()
        assert "both sides" in grade.sentence
        assert "zero" in grade.sentence
