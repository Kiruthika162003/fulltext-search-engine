from __future__ import annotations

import pytest

from quarry.errors import Invalid, Stale
from quarry.hybridclock import HybridClock, Stamp, happened_before


class TestLocalTime:
    def test_advancing_physical_time_resets_the_counter(self):
        clock = HybridClock(node="a")
        first = clock.now(100)
        second = clock.now(105)
        assert first.key() == (100, 0)
        assert second.key() == (105, 0)

    def test_the_same_millisecond_still_orders(self):
        clock = HybridClock(node="a")
        first = clock.now(100)
        second = clock.now(100)
        assert happened_before(first, second)
        assert second.key() == (100, 1)

    def test_backward_jumps_are_absorbed_not_replayed(self):
        clock = HybridClock(node="a")
        clock.now(100)
        jumped = clock.now(90)
        assert jumped.key() == (100, 1)
        assert clock.backward_jumps == 1
        assert "absorbed 1 backward jump(s)" in clock.health()

    def test_stamps_never_run_before_the_epoch(self):
        with pytest.raises(Invalid, match="before the epoch"):
            Stamp(physical=-1, logical=0)


class TestMerging:
    def test_receiving_steps_past_both_sides(self):
        clock = HybridClock(node="a")
        clock.now(100)
        merged = clock.receive(
            Stamp(physical=100, logical=5), observed_physical=100
        )
        assert merged.key() == (100, 6)

    def test_a_newer_remote_physical_wins(self):
        clock = HybridClock(node="a")
        clock.now(100)
        merged = clock.receive(
            Stamp(physical=140, logical=2), observed_physical=100
        )
        assert merged.key() == (140, 3)

    def test_a_newer_local_wall_clock_wins_clean(self):
        clock = HybridClock(node="a")
        clock.now(100)
        merged = clock.receive(
            Stamp(physical=100, logical=9), observed_physical=200
        )
        assert merged.key() == (200, 0)

    def test_the_drift_guard_refuses_the_future(self):
        clock = HybridClock(node="a")
        clock.now(100)
        with pytest.raises(Stale, match="inherits the lie"):
            clock.receive(
                Stamp(physical=5000, logical=0),
                observed_physical=100,
            )


class TestOrdering:
    def test_order_is_total_and_stable(self):
        stamps = [
            Stamp(100, 1),
            Stamp(100, 0),
            Stamp(99, 7),
            Stamp(101, 0),
        ]
        ordered = sorted(stamps, key=lambda held: held.key())
        assert [held.render() for held in ordered] == [
            "99.7",
            "100.0",
            "100.1",
            "101.0",
        ]
