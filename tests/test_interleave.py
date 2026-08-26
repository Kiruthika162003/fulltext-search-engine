from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.interleave import InterleaveExperiment, team_draft

LEFT = [10, 11, 12, 13]
RIGHT = [20, 21, 22, 23]


class TestTheDraft:
    def test_alternating_picks_with_the_coin(self):
        drafted = team_draft(LEFT, RIGHT, coin=[True], length=4)
        assert drafted.documents == (10, 20, 11, 21)
        assert drafted.supplied_by == ("left", "right", "left", "right")

    def test_the_coin_flips_the_draft_order(self):
        drafted = team_draft(LEFT, RIGHT, coin=[False], length=4)
        assert drafted.documents == (20, 10, 21, 11)

    def test_shared_documents_are_taken_once(self):
        drafted = team_draft([1, 2, 3], [2, 3, 4], coin=[True], length=6)
        assert drafted.documents == (1, 2, 3, 4)
        assert len(set(drafted.documents)) == len(drafted.documents)

    def test_the_draft_stops_when_both_wells_run_dry(self):
        drafted = team_draft([1], [2], coin=[True], length=10)
        assert drafted.documents == (1, 2)

    def test_an_empty_coin_is_refused(self):
        with pytest.raises(Invalid, match="coin"):
            team_draft(LEFT, RIGHT, coin=[], length=4)

    def test_zero_length_is_refused(self):
        with pytest.raises(Invalid):
            team_draft(LEFT, RIGHT, coin=[True], length=0)


class TestTheExperiment:
    def test_clicks_credit_the_supplying_team(self):
        experiment = InterleaveExperiment(coin=[True])
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[10, 11], length=4)
        assert experiment.credits == {"left": 2}

    def test_a_click_on_the_unshown_blames_instrumentation(self):
        experiment = InterleaveExperiment(coin=[True])
        with pytest.raises(Invalid, match="never shown"):
            experiment.serve_and_observe(LEFT, RIGHT, clicked=[99], length=4)

    def test_the_verdict_needs_its_margin(self):
        experiment = InterleaveExperiment(coin=[True])
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[10], length=4)
        assert "noise wearing a medal" in experiment.verdict()

    def test_a_clear_winner_is_crowned_with_the_score(self):
        experiment = InterleaveExperiment(coin=[True, False])
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[10, 11], length=4)
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[10, 12], length=6)
        assert experiment.verdict() == "left wins 4 to 0"

    def test_a_margin_under_one_is_refused(self):
        experiment = InterleaveExperiment(coin=[True])
        with pytest.raises(Invalid, match="coin flip"):
            experiment.verdict(margin=0)

    def test_impressions_are_counted(self):
        experiment = InterleaveExperiment(coin=[True])
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[], length=4)
        experiment.serve_and_observe(LEFT, RIGHT, clicked=[], length=4)
        assert experiment.impressions == 2
