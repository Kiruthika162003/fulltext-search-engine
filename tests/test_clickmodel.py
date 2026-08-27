from __future__ import annotations

import pytest

from quarry.clickmodel import (
    ClickModel,
    examination_rate,
)
from quarry.errors import Invalid


class TestExamination:
    def test_the_rates_decay_down_the_page(self):
        assert examination_rate(1) == 1.0
        assert examination_rate(2) == 0.7
        assert examination_rate(5) == 0.25

    def test_deep_positions_keep_shrinking(self):
        assert examination_rate(6) == 0.125
        assert examination_rate(7) < examination_rate(6)

    def test_position_zero_is_nowhere(self):
        with pytest.raises(Invalid, match="nowhere"):
            examination_rate(0)


class TestObservation:
    def test_a_click_at_the_bottom_outweighs_habit_at_the_top(self):
        model = ClickModel()
        for _ in range(4):
            model.observe("q", shown=[1, 2, 3], clicked={3})
        assert model.attraction("q", 3) == 1.0
        assert model.attraction("q", 1) == 0.0

    def test_skips_above_a_click_are_negative_evidence(self):
        model = ClickModel()
        for _ in range(4):
            model.observe("q", shown=[1, 2], clicked={2})
        held = model.table[("q", 1)]
        assert held.credit == 0.0
        assert held.weight == 4.0

    def test_results_below_the_last_click_stay_unjudged(self):
        model = ClickModel()
        model.observe("q", shown=[1, 2, 3], clicked={1})
        assert model.table[("q", 3)].weight == 0.0

    def test_clicks_on_the_unshown_expose_spliced_logs(self):
        model = ClickModel()
        with pytest.raises(Invalid, match="spliced"):
            model.observe("q", shown=[1, 2], clicked={9})

    def test_empty_impressions_teach_nothing(self):
        with pytest.raises(Invalid, match="teaches nothing"):
            ClickModel().observe("q", shown=[], clicked=set())


class TestEstimates:
    def test_position_correction_boosts_deep_clicks(self):
        model = ClickModel()
        model.observe("q", shown=[1, 2, 3, 4, 5], clicked={5})
        held = model.table[("q", 5)]
        assert held.credit == 1.0
        assert held.weight == 0.25
        assert model.attraction("q", 5) == 1.0

    def test_thin_evidence_is_not_confident(self):
        model = ClickModel()
        model.observe("q", shown=[1, 2], clicked={1})
        assert not model.confident("q", 1)
        for _ in range(3):
            model.observe("q", shown=[1, 2], clicked={1})
        assert model.confident("q", 1)

    def test_the_unseen_have_zero_attraction(self):
        assert ClickModel().attraction("q", 42) == 0.0


class TestTheReport:
    def test_the_report_flags_anecdotes(self):
        model = ClickModel()
        model.observe("q", shown=[1, 2], clicked={2})
        page = model.report("q")
        assert "[thin evidence]" in page

    def test_the_report_ranks_by_attraction(self):
        model = ClickModel()
        for _ in range(4):
            model.observe("q", shown=[1, 2], clicked={2})
            model.observe("q", shown=[2, 1], clicked={2})
        lines = model.report("q").splitlines()
        assert lines[0].startswith("doc 2")

    def test_no_evidence_says_so(self):
        assert ClickModel().report("q") == "no evidence yet for 'q'"
