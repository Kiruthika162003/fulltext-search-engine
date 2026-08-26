from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.fuzzy import FuzzyIndex, did_you_mean, edit_distance, suggest


def stocked() -> FuzzyIndex:
    index = FuzzyIndex()
    index.admit("cats", weight=50)
    index.admit("catz", weight=1)
    index.admit("cart", weight=10)
    index.admit("dog", weight=30)
    index.admit("xylophone", weight=2)
    return index


class TestEditDistance:
    def test_the_classics(self):
        assert edit_distance("kitten", "sitting", cap=3) == 3
        assert edit_distance("cat", "cat") == 0
        assert edit_distance("cat", "cats") == 1
        assert edit_distance("cat", "act", cap=2) == 2

    def test_the_band_stops_early(self):
        assert edit_distance("short", "completely different", cap=2) == 3

    def test_the_length_gap_is_a_free_refusal(self):
        assert edit_distance("a", "abcdefgh", cap=2) == 3

    def test_a_negative_cap_is_refused(self):
        with pytest.raises(Invalid):
            edit_distance("a", "b", cap=-1)


class TestTheNet:
    def test_the_shortlist_shares_grams(self):
        shortlist, skipped = stocked().shortlist("catz")
        assert "cats" in shortlist
        assert "xylophone" not in shortlist
        assert skipped >= 1

    def test_the_skip_count_keeps_the_shortcut_honest(self):
        shortlist, skipped = stocked().shortlist("zzzz")
        assert shortlist == []
        assert skipped == stocked().vocabulary_size()

    def test_empty_terms_are_refused(self):
        with pytest.raises(Invalid):
            FuzzyIndex().admit("")


class TestSuggestions:
    def test_popularity_breaks_the_distance_tie(self):
        best = suggest(stocked(), "catz", limit=2)
        assert best[0].term == "catz"
        assert best[0].distance == 0
        ranked = suggest(stocked(), "cots", limit=2)
        assert ranked[0].term == "cats"

    def test_far_terms_never_appear(self):
        terms = [held.term for held in suggest(stocked(), "cats", cap=1)]
        assert "xylophone" not in terms

    def test_zero_suggestions_is_refused(self):
        with pytest.raises(Invalid):
            suggest(stocked(), "cat", limit=0)


class TestDidYouMean:
    def test_a_typo_earns_the_common_correction(self):
        assert did_you_mean(stocked(), "cots") == "cats"

    def test_an_exact_hit_suggests_nothing(self):
        assert did_you_mean(stocked(), "cats") is None
        assert did_you_mean(stocked(), "catz") is None

    def test_popularity_settles_the_equidistant(self):
        assert did_you_mean(stocked(), "cars") == "cats"
        assert did_you_mean(stocked(), "dogg") == "dog"

    def test_gibberish_gets_silence_not_a_guess(self):
        assert did_you_mean(stocked(), "qqqq") is None
