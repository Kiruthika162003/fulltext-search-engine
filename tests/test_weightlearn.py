from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.weightlearn import JudgedPair, WeightLearner


def title_beats_body_pairs() -> list[JudgedPair]:
    return [
        JudgedPair(
            winner={"title": 1.0, "body": 0.0},
            loser={"title": 0.0, "body": 1.0},
        ),
        JudgedPair(
            winner={"title": 0.8, "body": 0.2},
            loser={"title": 0.1, "body": 0.9},
        ),
        JudgedPair(
            winner={"title": 0.6},
            loser={"body": 0.7},
        ),
    ]


class TestLearning:
    def test_the_lesson_lands_in_the_weights(self):
        learner = WeightLearner(field_names=("title", "body"))
        learner.train(title_beats_body_pairs())
        assert learner.weights["title"] > learner.weights["body"]

    def test_training_resolves_all_consistent_pairs(self):
        learner = WeightLearner(field_names=("title", "body"))
        page = learner.train(title_beats_body_pairs())
        assert page.endswith("wrong on 0 of 3 training pair(s)")

    def test_weights_stay_nonnegative(self):
        learner = WeightLearner(field_names=("title", "body"))
        learner.train(title_beats_body_pairs())
        assert all(weight >= 0 for weight in learner.weights.values())

    def test_weights_normalize_to_the_field_count(self):
        learner = WeightLearner(field_names=("title", "body"))
        learner.train(title_beats_body_pairs())
        assert round(sum(learner.weights.values()), 2) == 2.0


class TestRefusals:
    def test_no_pairs_learn_nothing(self):
        with pytest.raises(Invalid, match="learns nothing"):
            WeightLearner(field_names=("title",)).train([])

    def test_stray_fields_are_named(self):
        learner = WeightLearner(field_names=("title",))
        with pytest.raises(Invalid, match="unweighted field"):
            learner.train(
                [
                    JudgedPair(
                        winner={"title": 1.0},
                        loser={"footer": 0.5},
                    )
                ]
            )

    def test_no_fields_means_nothing_to_weight(self):
        with pytest.raises(Invalid, match="nothing to weight"):
            WeightLearner(field_names=())


class TestHonestReporting:
    def test_contradictory_pairs_stay_in_the_report(self):
        learner = WeightLearner(field_names=("title", "body"))
        contradiction = [
            JudgedPair(
                winner={"title": 1.0},
                loser={"body": 1.0},
            ),
            JudgedPair(
                winner={"body": 1.0},
                loser={"title": 1.0},
            ),
        ]
        page = learner.train(contradiction)
        assert "still wrong on 2 of 2" in page
