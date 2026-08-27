from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.health import (
    CheckResult,
    HealthBoard,
    index_canary_check,
    latency_check,
)


def green(name: str) -> CheckResult:
    return CheckResult(name=name, state="healthy", evidence="fine")


class TestChecks:
    def test_unknown_states_are_refused(self):
        with pytest.raises(Invalid):
            CheckResult(name="x", state="okayish", evidence="?")

    def test_the_canary_actually_flies(self):
        result = index_canary_check()()
        assert result.state == "healthy"
        assert "found one canary" in result.evidence

    def test_latency_grades_in_three_states(self):
        assert latency_check("q", 50, budget=100)().state == "healthy"
        assert latency_check("q", 150, budget=100)().state == "degraded"
        assert latency_check("q", 300, budget=100)().state == "failing"


class TestTheBoard:
    def test_the_aggregate_is_the_worst_never_the_average(self):
        board = HealthBoard()
        board.register("a", lambda: green("a"))
        board.register("b", lambda: green("b"))
        board.register(
            "c",
            lambda: CheckResult(
                name="c", state="failing", evidence="broken"
            ),
        )
        assert board.aggregate() == "failing"

    def test_all_green_aggregates_green(self):
        board = HealthBoard()
        board.register("a", lambda: green("a"))
        assert board.aggregate() == "healthy"

    def test_a_crashing_check_reports_as_failing_not_as_a_crash(self):
        board = HealthBoard()

        def broken() -> CheckResult:
            raise Invalid("the checker lost its own canary")

        board.register("fragile", broken)
        results = board.run()
        assert results[0].state == "failing"
        assert "the check itself refused" in results[0].evidence

    def test_double_registration_is_refused(self):
        board = HealthBoard()
        board.register("a", lambda: green("a"))
        with pytest.raises(Invalid):
            board.register("a", lambda: green("a"))

    def test_an_empty_board_has_no_opinion(self):
        with pytest.raises(Invalid, match="no opinion"):
            HealthBoard().aggregate()

    def test_the_page_leads_with_the_worst(self):
        board = HealthBoard()
        board.register("a", lambda: green("a"))
        board.register(
            "b",
            lambda: CheckResult(
                name="b", state="degraded", evidence="slower"
            ),
        )
        page = board.page()
        assert page.splitlines()[0] == "overall: degraded"
        assert "  a: healthy (fine)" in page
