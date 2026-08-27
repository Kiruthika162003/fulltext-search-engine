from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.featureflags import Flag, FlagBoard


def new_ranker() -> Flag:
    return Flag(
        name="bm25-retune",
        owner="relevance-team",
        kill_condition="shipped to 100% or canary rolls back",
        review_day=100,
        rollout_share=0.2,
    )


def board() -> FlagBoard:
    held = FlagBoard()
    held.declare(new_ranker())
    return held


class TestDeclaration:
    def test_ownerless_flags_outlive_their_authors(self):
        with pytest.raises(Invalid, match="outlives\\s+its author|name one"):
            Flag(
                name="x",
                owner=" ",
                kill_condition="never",
                review_day=1,
            )

    def test_kill_conditions_are_mandatory(self):
        with pytest.raises(Invalid, match="when it dies"):
            Flag(
                name="x",
                owner="me",
                kill_condition="  ",
                review_day=1,
            )

    def test_redeclaring_is_refused(self):
        held = board()
        with pytest.raises(Invalid, match="instead of redeclaring"):
            held.declare(new_ranker())


class TestAssignment:
    def test_a_user_experience_is_stable(self):
        held = board()
        first = held.serves("bm25-retune", "user-42")
        assert all(
            held.serves("bm25-retune", "user-42") == first
            for _ in range(5)
        )

    def test_the_share_is_roughly_honored(self):
        held = board()
        served = sum(
            1
            for n in range(1000)
            if held.serves("bm25-retune", f"user-{n}")
        )
        assert 140 <= served <= 260

    def test_unknown_flags_are_missing(self):
        with pytest.raises(Missing, match="no flag named"):
            board().serves("ghost", "user-1")


class TestRollout:
    def test_widening_only_widens(self):
        held = board()
        assert held.widen("bm25-retune", 0.5, "ops") == (
            "bm25-retune now at 50%"
        )
        with pytest.raises(Invalid, match="not a narrower share"):
            held.widen("bm25-retune", 0.3, "ops")

    def test_retreat_is_one_switch(self):
        held = board()
        held.disable("bm25-retune", "canary rolled back", "ops")
        assert not held.serves("bm25-retune", "user-42")
        with pytest.raises(Invalid, match="widens to nobody"):
            held.widen("bm25-retune", 0.9, "ops")

    def test_disabling_needs_a_reason(self):
        with pytest.raises(Invalid, match="guessing"):
            board().disable("bm25-retune", "  ", "ops")


class TestTheLedger:
    def test_the_journal_tells_the_story(self):
        held = board()
        held.widen("bm25-retune", 0.5, "ops")
        held.disable("bm25-retune", "canary rolled back", "ops")
        assert held.journal == [
            "bm25-retune declared by relevance-team, dies when "
            "shipped to 100% or canary rolls back",
            "bm25-retune widened 0.2 -> 0.5 by ops",
            "bm25-retune DISABLED by ops: canary rolled back",
        ]

    def test_flags_past_review_are_listed(self):
        overdue = board().past_review(today=150)
        assert overdue == [
            "bm25-retune: review was day 100, owner relevance-team"
        ]
        assert board().past_review(today=50) == []
