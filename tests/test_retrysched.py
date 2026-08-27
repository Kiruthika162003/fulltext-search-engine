from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.retrysched import MAX_WAIT, herd_spread, plan


class TestThePlan:
    def test_backoff_doubles_within_its_windows(self):
        held = plan("client-a")
        for attempt, wait in enumerate(held.waits_ms):
            ceiling = min(100 * (2**attempt), MAX_WAIT)
            assert ceiling // 2 <= wait <= ceiling

    def test_the_cap_holds_on_the_worst_day(self):
        held = plan("client-a")
        assert max(held.waits_ms) <= MAX_WAIT

    def test_the_same_caller_replays_the_same_plan(self):
        assert plan("client-a") == plan("client-a")

    def test_different_callers_jitter_apart(self):
        assert plan("client-a").waits_ms != plan("client-b").waits_ms

    def test_the_page_ends_in_a_named_give_up(self):
        page = plan("client-a", attempts=3).page()
        assert page.startswith("retry plan for client-a:")
        assert "attempt 3: wait" in page
        assert "then GIVE UP after 3 attempt(s)" in page


class TestContracts:
    def test_nameless_callers_join_the_herd(self):
        with pytest.raises(Invalid, match="herd"):
            plan("  ")

    def test_endless_retries_are_outage_generators(self):
        with pytest.raises(Invalid, match="patience"):
            plan("client-a", attempts=99)
        with pytest.raises(Invalid, match="patience"):
            plan("client-a", attempts=0)


class TestTheHerd:
    def test_a_fleet_spreads_instead_of_thundering(self):
        callers = [f"client-{n}" for n in range(30)]
        page = herd_spread(callers, attempt=3)
        assert "30 callers spread over" in page
        distinct = int(page.split("with ")[1].split(" distinct")[0])
        assert distinct >= 20

    def test_a_herd_of_one_cannot_thunder(self):
        with pytest.raises(Invalid, match="cannot thunder"):
            herd_spread(["alone"], attempt=0)
