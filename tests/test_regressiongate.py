from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.evals.grade import Grade
from quarry.evals.registry import all_grades
from quarry.regressiongate import gate, pair_grades


def grade(name: str, holds: bool) -> Grade:
    return Grade(eval_name=name, sentence="s", holds=holds)


class TestPairing:
    def test_vanished_evals_are_not_passes(self):
        with pytest.raises(Invalid, match="not the same as passing"):
            pair_grades(
                [grade("a", True), grade("b", True)],
                [grade("a", True)],
            )

    def test_new_evals_gate_on_their_own_result(self):
        pairs = pair_grades([grade("a", True)], [grade("a", True), grade("b", False)])
        fresh = next(p for p in pairs if p.eval_name == "b")
        assert fresh.state() == "REGRESSED"


class TestVerdicts:
    def test_held_to_broken_blocks_the_ship(self):
        verdict = gate(
            [grade("a", True), grade("b", True)],
            [grade("a", True), grade("b", False)],
        )
        assert not verdict.ships
        assert verdict.regressions == ("b",)
        assert verdict.report().startswith(
            "BLOCKED: regressed eval(s): b"
        )

    def test_standing_debt_blocks_nothing_new(self):
        verdict = gate(
            [grade("a", True), grade("b", False)],
            [grade("a", True), grade("b", False)],
        )
        assert verdict.ships
        assert verdict.debt == ("b",)
        assert "standing debt" in verdict.report()

    def test_healing_is_celebrated(self):
        verdict = gate(
            [grade("a", False)],
            [grade("a", True)],
        )
        assert verdict.ships
        assert verdict.healed == ("a",)
        assert "healed this build: a" in verdict.report()

    def test_zero_evals_approve_anything_so_refuse(self):
        with pytest.raises(Invalid, match="approves anything"):
            gate([grade("a", True)], [])


class TestAgainstTheRealRegistry:
    def test_the_current_registry_ships_against_itself(self):
        grades = all_grades()
        verdict = gate(grades, grades)
        assert verdict.ships
        assert verdict.regressions == ()
        assert verdict.debt == ()
