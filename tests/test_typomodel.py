from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.typomodel import adjacent, correct, typo_cost


class TestTheKeyboard:
    def test_neighbors_are_neighbors(self):
        assert adjacent("q", "w")
        assert adjacent("s", "w")
        assert adjacent("g", "b")

    def test_across_the_board_is_not_a_slip(self):
        assert not adjacent("q", "p")
        assert not adjacent("a", "l")

    def test_a_key_is_not_its_own_neighbor(self):
        assert not adjacent("k", "k")


class TestPricing:
    def test_identical_words_cost_nothing(self):
        assert typo_cost("kettle", "kettle") == 0.0

    def test_adjacent_slips_are_cheap(self):
        assert typo_cost("kwttle", "kettle") == 0.4

    def test_distant_substitutions_pay_full_price(self):
        assert typo_cost("kpttle", "kettle") == 1.0

    def test_neighbor_transpositions_are_cheap(self):
        assert typo_cost("esrver", "server") == 0.4

    def test_distant_transpositions_pay_full_price(self):
        assert typo_cost("ekttle", "kettle") == 1.0
        assert typo_cost("saerch", "search") == 1.0

    def test_doubled_letters_are_cheap_to_drop(self):
        assert typo_cost("kettlle", "kettle") == 0.4

    def test_empty_spellings_are_refused(self):
        with pytest.raises(Invalid, match="both spellings"):
            typo_cost("", "kettle")


DICTIONARY = {
    "kettle": 50,
    "nettle": 400,
    "settle": 90,
    "search": 800,
}


class TestCorrection:

    def test_the_mechanical_explanation_beats_popularity(self):
        ranked = correct("kwttle", DICTIONARY)
        assert ranked[0].word == "kettle"

    def test_frequency_breaks_true_ties(self):
        ranked = correct("cettle", DICTIONARY)
        by_word = {held.word: held.cost for held in ranked}
        assert by_word["kettle"] == by_word["nettle"] == 1.0
        assert by_word["settle"] == 0.4
        assert ranked[0].word == "settle"
        nettle_pos = [held.word for held in ranked].index("nettle")
        kettle_pos = [held.word for held in ranked].index("kettle")
        assert nettle_pos < kettle_pos

    def test_exact_matches_are_not_corrections(self):
        ranked = correct("search", DICTIONARY)
        assert all(held.word != "search" for held in ranked)

    def test_the_budget_is_a_fence(self):
        ranked = correct("zzzzzz", DICTIONARY)
        assert ranked == []

    def test_empty_dictionaries_are_refused(self):
        with pytest.raises(Invalid, match="empty dictionary"):
            correct("kettle", {})
