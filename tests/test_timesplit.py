from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.timesplit import (
    Stamped,
    cut_at_boundary_rule,
    leakage_audit,
    split,
)


def month() -> list[Stamped]:
    return [
        Stamped(key=f"q{n}", day=n) for n in range(30)
    ]


class TestSplitting:
    def test_the_cut_is_a_single_timestamp(self):
        train, test = split(month(), cut_day=15)
        assert max(held.day for held in train) == 14
        assert min(held.day for held in test) == 15

    def test_the_boundary_record_goes_to_test(self):
        _, test = split(month(), cut_day=15)
        assert any(held.day == 15 for held in test)
        assert "go to TEST" in cut_at_boundary_rule()

    def test_thin_sides_are_anecdotes_with_axes(self):
        with pytest.raises(Invalid, match="anecdote with an axis"):
            split(month(), cut_day=25)

    def test_splitting_nothing_is_refused(self):
        with pytest.raises(Invalid, match="trains nothing"):
            split([], cut_day=5)


class TestLeakage:
    def test_a_clean_split_is_certified(self):
        train, test = split(month(), cut_day=15)
        page = leakage_audit(train, test)
        assert page == (
            "clean split: train ends day 14, test begins day 15, "
            "no shared keys"
        )

    def test_shared_keys_are_leakage(self):
        train, test = split(month(), cut_day=15)
        poisoned = [*train, Stamped(key="q20", day=3)]
        with pytest.raises(Invalid, match="LEAKAGE"):
            leakage_audit(poisoned, test)

    def test_time_leaks_are_their_own_crime(self):
        train = [Stamped(key=f"a{n}", day=20) for n in range(10)]
        test = [Stamped(key=f"b{n}", day=15) for n in range(10)]
        with pytest.raises(Invalid, match="own future"):
            leakage_audit(train, test)

    def test_the_leak_list_caps_at_five(self):
        train = [Stamped(key=f"q{n}", day=1) for n in range(12)]
        test = [Stamped(key=f"q{n}", day=9) for n in range(12)]
        with pytest.raises(Invalid, match="and 7 more"):
            leakage_audit(train, test)
