from __future__ import annotations

import pytest

from quarry.bisector import Bisection
from quarry.errors import Invalid

BUILDS = [f"build-{n}" for n in range(40)]


def broke_at(bad_from: int):
    return lambda build: int(build.split("-")[1]) < bad_from


class TestTheHunt:
    def test_the_first_bad_build_is_named_with_its_predecessor(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(23))
        answer = hunt.hunt()
        assert "first bad: build-23" in answer
        assert "predecessor build-22" in answer

    def test_forty_builds_take_few_probes(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(23))
        hunt.hunt()
        assert hunt.probes <= 9

    def test_the_journal_is_the_receipt(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(23))
        hunt.hunt()
        page = hunt.transcript()
        assert "probe 1: build-0 is good" in page
        assert "build-39 is BAD" in page

    def test_a_break_at_the_first_step_is_found(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(1))
        assert "first bad: build-1" in hunt.hunt()


class TestBadAssumptions:
    def test_an_all_bad_history_widens_the_range(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(0))
        with pytest.raises(Invalid, match="widen the range"):
            hunt.hunt()

    def test_an_all_good_history_has_no_regression(self):
        hunt = Bisection(builds=BUILDS, verdict=broke_at(99))
        with pytest.raises(Invalid, match="no regression"):
            hunt.hunt()

    def test_a_flaky_verdict_aborts_loudly(self):
        answers = iter([True, False, False])

        def coin_flip(build: str) -> bool:
            try:
                return next(answers)
            except StopIteration:
                return False

        hunt = Bisection(builds=BUILDS, verdict=coin_flip)
        with pytest.raises(Invalid, match="coin flip"):
            hunt.hunt()

    def test_one_build_is_just_looking(self):
        hunt = Bisection(builds=["only"], verdict=lambda b: True)
        with pytest.raises(Invalid, match="just looking"):
            hunt.hunt()
