from __future__ import annotations

import pytest

from quarry.backpressure import Backpressure
from quarry.errors import Frozen, Invalid


def filled_to(count: int, capacity: int = 20) -> Backpressure:
    held = Backpressure(capacity=capacity)
    for _ in range(count):
        held.admit(urgent=True)
    return held


class TestStages:
    def test_green_admits_quietly(self):
        held = Backpressure(capacity=20)
        assert held.admit() == "admitted"
        assert held.stage == "green"

    def test_amber_asks_for_half_speed(self):
        held = filled_to(9)
        message = held.admit()
        assert "halve your send rate" in message
        assert held.stage == "amber"

    def test_red_refuses_bulk_but_admits_singles(self):
        held = filled_to(15)
        with pytest.raises(Frozen, match=r"bulk traffic waits"):
            held.admit(bulk=True)
        assert "admitted" in held.admit()

    def test_black_admits_only_urgent(self):
        held = filled_to(18)
        with pytest.raises(Frozen, match="stage black"):
            held.admit()
        held.admit(urgent=True)
        assert held.filled == 19

    def test_a_full_buffer_only_flushes(self):
        held = filled_to(20)
        with pytest.raises(Frozen, match="only a flush"):
            held.admit(urgent=True)


class TestHysteresis:
    def test_descent_needs_the_lower_floor(self):
        held = filled_to(15)
        held.admit()
        assert held.stage == "red"
        held.flush(drained=3)
        assert held.stage == "red"
        held.flush(drained=2)
        assert held.stage == "amber"

    def test_a_deep_flush_lands_back_at_green(self):
        held = filled_to(19)
        held.flush(drained=15)
        assert held.stage == "green"

    def test_the_flush_reports_the_journey(self):
        held = filled_to(19)
        message = held.flush(drained=15)
        assert message == "drained 15; stage black -> green"


class TestHonestArithmetic:
    def test_zero_capacity_is_a_wall(self):
        with pytest.raises(Invalid, match="wall"):
            Backpressure(capacity=0)

    def test_draining_nothing_is_a_lie(self):
        with pytest.raises(Invalid, match="no-op lie"):
            filled_to(5).flush(drained=0)

    def test_draining_more_than_held_invents_documents(self):
        with pytest.raises(Invalid, match="invents"):
            filled_to(5).flush(drained=9)

    def test_the_ledger_counts_time_and_refusals(self):
        held = filled_to(18)
        held.tick()
        with pytest.raises(Frozen):
            held.admit()
        held.tick()
        page = held.ledger()
        assert "black: 2" in page
        assert "1 refusal(s)" in page
