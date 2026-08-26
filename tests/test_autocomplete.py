from __future__ import annotations

import pytest

from quarry.autocomplete import (
    Completer,
    Completion,
    stable_between_keystrokes,
)
from quarry.errors import Invalid


def stocked() -> Completer:
    completer = Completer()
    completer.admit("cat", weight=50)
    completer.admit("cat food", weight=30)
    completer.admit("cat toys", weight=30)
    completer.admit("catamaran", weight=5)
    completer.admit("dog", weight=40)
    return completer


class TestAdmission:
    def test_weights_accumulate_per_term(self):
        completer = stocked()
        completer.admit("cat", weight=10)
        assert completer.complete("cat")[0] == Completion(
            term="cat", weight=60
        )

    def test_terms_are_counted_once(self):
        completer = stocked()
        before = completer.terms_held
        completer.admit("cat", weight=1)
        assert completer.terms_held == before

    def test_empty_terms_and_zero_weights_are_refused(self):
        with pytest.raises(Invalid):
            Completer().admit("")
        with pytest.raises(Invalid):
            Completer().admit("cat", weight=0)


class TestCompletion:
    def test_the_prefix_walk_collects_the_subtree(self):
        found = [held.term for held in stocked().complete("cat")]
        assert found == ["cat", "cat food", "cat toys", "catamaran"]

    def test_weight_ranks_and_ties_break_alphabetically(self):
        found = stocked().complete("cat", limit=3)
        assert [held.term for held in found] == [
            "cat",
            "cat food",
            "cat toys",
        ]

    def test_a_dead_prefix_returns_empty_not_error(self):
        assert stocked().complete("zeb") == []

    def test_the_empty_prefix_is_refused_with_directions(self):
        with pytest.raises(Invalid, match="popular"):
            stocked().complete("")

    def test_popular_is_the_honest_name_for_the_chart(self):
        chart = stocked().popular(limit=2)
        assert [held.term for held in chart] == ["cat", "dog"]

    def test_zero_limits_are_refused(self):
        with pytest.raises(Invalid):
            stocked().complete("cat", limit=0)
        with pytest.raises(Invalid):
            stocked().popular(limit=0)


class TestStability:
    def test_the_dropdown_never_reshuffles_mid_word(self):
        assert stable_between_keystrokes(stocked(), "c")
        assert stable_between_keystrokes(stocked(), "ca")

    def test_prefix_existence_is_a_cheap_probe(self):
        completer = stocked()
        assert completer.prefix_exists("cata")
        assert not completer.prefix_exists("catz")
