from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.launchboard import LaunchBoard


def reported(
    regression: bool = True,
    shadow: bool = True,
    canary: bool = True,
    freeze: bool = True,
) -> LaunchBoard:
    board = LaunchBoard(build="build-88")
    board.report_gate(
        "regression", regression, "no eval that held went broken"
    )
    board.report_gate(
        "shadow", shadow, "97% agreement over 60 queries"
    )
    board.report_gate("canary", canary, "SHIP: gaps inside tolerance")
    board.report_gate("freeze", freeze, "no window covers today")
    return board


class TestVerdicts:
    def test_four_greens_are_a_go(self):
        board = reported()
        assert board.go()
        assert board.page().endswith(
            "VERDICT: GO, all four gates green"
        )

    def test_three_greens_and_a_red_is_a_red(self):
        board = reported(canary=False)
        assert not board.go()
        assert "VERDICT: NO GO (canary red)" in board.page()

    def test_silence_is_not_a_pass(self):
        board = LaunchBoard(build="build-88")
        board.report_gate("regression", True, "clean")
        page = board.page()
        assert "[RED] shadow: not reported" in page
        assert "silence is not\na pass" in page or "silence is not" in page
        assert not board.go()
        assert board.unreported() == ["shadow", "canary", "freeze"]


class TestTheDoor:
    def test_unknown_gates_are_named(self):
        with pytest.raises(Missing, match="not a launch gate"):
            LaunchBoard(build="b").report_gate("vibes", True, "good")

    def test_wordless_verdicts_cannot_be_argued_with(self):
        with pytest.raises(Invalid, match="argued with"):
            LaunchBoard(build="b").report_gate(
                "canary", True, "  "
            )

    def test_second_opinions_go_on_fresh_boards(self):
        board = reported()
        with pytest.raises(Invalid, match="fresh board"):
            board.report_gate("canary", False, "changed my mind")

    def test_buildless_boards_ship_wrong_builds(self):
        with pytest.raises(Invalid, match="wrong builds ship"):
            LaunchBoard(build="  ")


class TestThePage:
    def test_the_evidence_travels_with_the_decision(self):
        page = reported().page()
        assert page.startswith("launch board for build-88:")
        assert "[GREEN] shadow: 97% agreement over 60 queries" in page
        assert "[GREEN] freeze: no window covers today" in page
