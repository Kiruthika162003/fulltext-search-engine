from __future__ import annotations

import pytest

from quarry.deadline import BudgetClock, DeadlineSearcher
from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def layered() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema, flush_at=100)
    for number in range(8):
        index.add({"body": f"cat story {number} in the big segment"})
    index.flush()
    for number in range(8, 11):
        index.add({"body": f"cat story {number} in the small segment"})
    index.flush()
    return index


class TestTheClock:
    def test_charges_accumulate_toward_the_budget(self):
        clock = BudgetClock(budget=10)
        clock.charge(4)
        assert not clock.expired()
        assert clock.remaining() == 6
        clock.charge(6)
        assert clock.expired()

    def test_a_zero_budget_has_already_passed(self):
        with pytest.raises(Invalid):
            BudgetClock(budget=0)

    def test_time_does_not_rewind(self):
        with pytest.raises(Invalid):
            BudgetClock(budget=5).charge(-1)


class TestDeadlineSearch:
    def test_a_roomy_budget_answers_completely(self):
        searcher = DeadlineSearcher(index=layered())
        page = searcher.search(parse("cat"), BudgetClock(budget=100))
        assert page.complete
        assert len(page.externals) == 10
        assert page.docs_unreached == 0

    def test_big_segments_walk_first(self):
        searcher = DeadlineSearcher(index=layered())
        page = searcher.search(parse("cat"), BudgetClock(budget=8))
        assert page.segments_reached == ("seg0",)
        assert page.segments_unreached == ("seg1",)

    def test_the_partial_flag_cannot_be_missed(self):
        searcher = DeadlineSearcher(index=layered())
        page = searcher.search(parse("cat"), BudgetClock(budget=8))
        assert not page.complete
        assert page.docs_unreached == 3

    def test_every_returned_hit_is_a_real_hit(self):
        searcher = DeadlineSearcher(index=layered())
        partial = searcher.search(parse("cat"), BudgetClock(budget=8))
        full = searcher.search(parse("cat"), BudgetClock(budget=100))
        assert set(partial.externals) <= set(full.externals)

    def test_the_partial_share_is_tracked(self):
        searcher = DeadlineSearcher(index=layered())
        searcher.search(parse("cat"), BudgetClock(budget=8))
        searcher.search(parse("cat"), BudgetClock(budget=100))
        assert searcher.partial_share() == 0.5

    def test_no_runs_refuses_the_share(self):
        with pytest.raises(Invalid, match="shrug"):
            DeadlineSearcher(index=layered()).partial_share()

    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            DeadlineSearcher(index=layered()).search(
                parse("cat"), BudgetClock(budget=10), limit=0
            )
