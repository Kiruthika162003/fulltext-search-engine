from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.gibberish import GibberishGate

CORPUS = (
    "the copper kettle rested on the warm stove while the "
    "evening light settled over the harbor and the market "
    "traders counted their quiet takings before the long walk "
    "home through the winter streets"
).split()

HOLDOUT = ["kettle", "harbor", "market", "winter", "evening"]


def trained() -> GibberishGate:
    gate = GibberishGate()
    gate.train(CORPUS, HOLDOUT)
    return gate


class TestTraining:
    def test_the_threshold_sits_under_the_worst_real_word(self):
        gate = trained()
        assert all(
            gate.score(word) >= gate.threshold for word in HOLDOUT
        )

    def test_thin_training_models_an_anecdote(self):
        with pytest.raises(Invalid, match="anecdote"):
            GibberishGate().train(["one", "two"], ["three"])

    def test_untrained_gates_judge_nobody(self):
        with pytest.raises(Invalid, match="judges nobody"):
            GibberishGate().score("kettle")


class TestJudgment:
    def test_real_words_walk_like_language(self):
        gate = trained()
        mash, words = gate.is_mash("streets")
        assert not mash
        assert "walks like language" in words

    def test_keyboard_mash_is_convicted(self):
        gate = trained()
        mash, words = gate.is_mash("zxqjvzxq")
        assert mash
        assert "mash" in words

    def test_novel_mash_needs_no_blocklist(self):
        gate = trained()
        assert gate.is_mash("qqfjzzxv")[0]
        assert gate.is_mash("xzxzxzxz")[0]

    def test_short_strings_pass_ungated(self):
        gate = trained()
        mash, words = gate.is_mash("zx")
        assert not mash
        assert "cannot convict" in words

    def test_letterless_strings_cannot_be_scored(self):
        with pytest.raises(Invalid, match="no letter pairs"):
            trained().score("12345")
