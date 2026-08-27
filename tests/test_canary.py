from __future__ import annotations

import pytest

from quarry.canary import (
    MIN_SEARCHES,
    ArmLedger,
    Canary,
    assigned_arm,
)
from quarry.errors import Invalid


class TestAssignment:
    def test_assignment_is_deterministic(self):
        assert assigned_arm("session-9") == assigned_arm("session-9")

    def test_the_share_is_roughly_honored(self):
        arms = [
            assigned_arm(f"session-{n}") for n in range(1000)
        ]
        canaries = arms.count("canary")
        assert 60 <= canaries <= 140

    def test_a_full_share_takes_everyone(self):
        assert assigned_arm("anyone", share=1.0) == "canary"

    def test_nameless_sessions_are_refused(self):
        with pytest.raises(Invalid, match="cannot be assigned"):
            assigned_arm("  ")


class TestLedgers:
    def test_rates_are_arithmetic(self):
        ledger = ArmLedger()
        ledger.observe(clicks=2)
        ledger.observe(clicks=0)
        assert ledger.abandonment() == 0.5
        assert ledger.clicks_per_search() == 1.0

    def test_empty_ledgers_refuse_rates(self):
        with pytest.raises(Invalid, match="not a number"):
            ArmLedger().abandonment()


def fed_canary(canary_clicks: int, incumbent_clicks: int) -> Canary:
    """Both arms filled directly; assignment is tested separately."""
    held = Canary()
    for _ in range(MIN_SEARCHES):
        held.ledgers["canary"].observe(canary_clicks)
        held.ledgers["incumbent"].observe(incumbent_clicks)
    return held


class TestVerdicts:
    def test_early_reads_refuse_with_the_counts(self):
        held = Canary()
        held.observe("session-1", clicks=1)
        with pytest.raises(Invalid, match="refuses to conclude"):
            held.verdict()
        assert not held.ready()

    def test_a_tie_ships(self):
        held = fed_canary(canary_clicks=1, incumbent_clicks=1)
        assert held.verdict().startswith("SHIP")

    def test_a_clear_win_ships(self):
        held = fed_canary(canary_clicks=2, incumbent_clicks=1)
        assert held.verdict().startswith("SHIP")

    def test_rising_abandonment_rolls_back(self):
        held = fed_canary(canary_clicks=1, incumbent_clicks=1)
        for _ in range(20):
            held.ledgers["canary"].observe(0)
            held.ledgers["incumbent"].observe(1)
        assert held.verdict().startswith("ROLL BACK")

    def test_the_verdict_shows_its_numbers(self):
        held = fed_canary(canary_clicks=1, incumbent_clicks=1)
        page = held.verdict()
        assert "abandonment" in page
        assert "clicks per search" in page
        assert "gap" in page

    def test_observation_routes_by_assignment(self):
        held = Canary()
        arm = held.observe("session-42", clicks=1)
        assert held.ledgers[arm].searches == 1
