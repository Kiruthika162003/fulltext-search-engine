from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.lifecycle import LifecycleEngine, LifecyclePolicy


def quarterly() -> LifecyclePolicy:
    return LifecyclePolicy(
        name="quarterly",
        read_only_after=30,
        unreplicated_after=60,
        delete_after=90,
    )


def engine() -> LifecycleEngine:
    held = LifecycleEngine(policy=quarterly())
    held.manage("logs-january", born_at=0)
    held.manage("logs-march", born_at=59)
    return held


class TestThePolicy:
    def test_phases_ladder_by_age(self):
        policy = quarterly()
        assert policy.phase_at(10) == "serving"
        assert policy.phase_at(30) == "read-only"
        assert policy.phase_at(60) == "unreplicated"
        assert policy.phase_at(90) == "deleted"

    def test_a_backwards_ladder_is_refused(self):
        with pytest.raises(Invalid, match="age forward"):
            LifecyclePolicy(
                name="bad",
                read_only_after=60,
                unreplicated_after=30,
                delete_after=90,
            )

    def test_zero_ages_are_refused(self):
        with pytest.raises(Invalid):
            LifecyclePolicy(
                name="bad",
                read_only_after=0,
                unreplicated_after=1,
                delete_after=2,
            )


class TestAdvancing:
    def test_transitions_fire_with_their_evidence(self):
        held = engine()
        acted = held.advance(now=61)
        assert (
            "logs-january: serving -> unreplicated (age 61, policy "
            "quarterly)" in acted
        )
        assert (
            "logs-march: serving -> read-only (age 2, policy "
            "quarterly)" not in acted
        )

    def test_deletion_happens_at_the_retention_line(self):
        held = engine()
        held.advance(now=95)
        assert held.deleted == ["logs-january"]
        assert "logs-january" not in held.managed

    def test_steady_state_acts_on_nothing(self):
        held = engine()
        held.advance(now=61)
        assert held.advance(now=61) == []


class TestHolds:
    def test_a_hold_freezes_every_transition(self):
        held = engine()
        held.hold("logs-january", reason="litigation 2026-114")
        held.advance(now=95)
        assert "logs-january" in held.managed
        assert held.managed["logs-january"].phase == "serving"

    def test_the_plan_shows_the_freeze_and_the_counterfactual(self):
        held = engine()
        held.hold("logs-january", reason="litigation 2026-114")
        plan = held.plan(now=95)
        assert (
            "logs-january: FROZEN by hold (litigation 2026-114); "
            "policy would say deleted" in plan
        )

    def test_a_reasonless_hold_is_refused(self):
        with pytest.raises(Invalid, match="lifted responsibly"):
            engine().hold("logs-january", reason="  ")

    def test_release_needs_a_holder_and_is_journaled(self):
        held = engine()
        held.hold("logs-january", reason="litigation 2026-114")
        held.release_hold("logs-january", who="counsel")
        assert any(
            "hold released by counsel" in line for line in held.journal
        )
        held.advance(now=95)
        assert held.deleted == ["logs-january"]

    def test_releasing_the_unheld_is_refused(self):
        with pytest.raises(Invalid, match="nothing to release"):
            engine().release_hold("logs-january", who="counsel")

    def test_ghost_indexes_are_named(self):
        with pytest.raises(Missing):
            engine().hold("ghost", reason="why not")
