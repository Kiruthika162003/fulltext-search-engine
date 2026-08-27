from __future__ import annotations

from quarry.evals import fuzzquality
from quarry.evals.registry import EVALS


class TestFuzzQuality:
    def test_the_grade_holds(self):
        assert fuzzquality.run().holds

    def test_every_one_slip_typo_finds_its_word(self):
        numbers = fuzzquality.run().numbers
        assert numbers["typo_hit_rate"] == 1.0
        assert numbers["typos_tested"] == 5

    def test_real_words_are_never_second_guessed(self):
        numbers = fuzzquality.run().numbers
        assert numbers["false_friend_rate"] == 0.0

    def test_the_eval_is_registered(self):
        assert "quarry.evals.fuzzquality" in EVALS
