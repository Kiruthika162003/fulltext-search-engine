from __future__ import annotations

import importlib

import pytest

from quarry.errors import Invalid
from quarry.evals.grade import (
    Grade,
    mean_reciprocal_rank,
    precision,
    recall,
    reciprocal_rank,
)
from quarry.evals.registry import EVALS, broken, report


class TestMetrics:
    def test_precision_is_of_the_returned(self):
        assert precision([1, 2, 3, 4], {1, 3, 9}) == 0.5

    def test_recall_is_of_the_relevant(self):
        assert recall([1, 2], {1, 3, 9}) == pytest.approx(0.3333, abs=1e-4)

    def test_reciprocal_rank_rewards_the_first_good_answer(self):
        assert reciprocal_rank([9, 1, 2], {1}) == 0.5
        assert reciprocal_rank([7, 8], {1}) == 0.0

    def test_mrr_averages_the_runs(self):
        runs = [([1], {1}), ([9, 1], {1})]
        assert mean_reciprocal_rank(runs) == 0.75

    def test_nothing_refuses_to_average(self):
        with pytest.raises(Invalid):
            precision([], {1})
        with pytest.raises(Invalid):
            recall([1], set())
        with pytest.raises(Invalid):
            mean_reciprocal_rank([])


class TestTheSuite:
    @pytest.mark.parametrize("dotted", EVALS)
    def test_each_eval_holds(self, dotted):
        grade = importlib.import_module(dotted).run()
        assert isinstance(grade, Grade)
        assert grade.holds, grade.line()

    def test_each_eval_names_itself(self):
        for dotted in EVALS:
            grade = importlib.import_module(dotted).run()
            assert grade.eval_name == dotted.rsplit(".", 1)[1]
            assert grade.numbers

    def test_nothing_is_broken(self):
        assert broken() == []

    def test_the_report_renders_every_line(self):
        page = report()
        for dotted in EVALS:
            assert dotted.rsplit(".", 1)[1] in page
        assert page.endswith("2 evals, 0 broken")
