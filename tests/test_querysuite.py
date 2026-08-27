from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.querysuite import GoldenSuite


def blessed_suite() -> GoldenSuite:
    suite = GoldenSuite()
    suite.bless(
        "cat food",
        observed=(3, 1, 7),
        who="meera",
        at=100,
        note="launch ranking reviewed by the search guild",
    )
    suite.bless(
        "winter boots",
        observed=(9, 2),
        who="meera",
        at=100,
        note="seasonal head query",
    )
    return suite


class TestBlessing:
    def test_blessings_are_journaled_with_who_and_why(self):
        suite = blessed_suite()
        assert (
            "[100] 'cat food' blessed by meera: launch ranking "
            "reviewed by the search guild" in suite.journal
        )

    def test_a_noteless_blessing_is_refused(self):
        with pytest.raises(Invalid, match="approves its own"):
            GoldenSuite().bless(
                "q", observed=(1,), who="x", at=0, note="  "
            )

    def test_blessing_emptiness_enshrines_a_broken_query(self):
        with pytest.raises(Invalid, match="enshrines"):
            GoldenSuite().bless(
                "q", observed=(), who="x", at=0, note="why"
            )


class TestComparison:
    def test_the_three_verdicts_escalate(self):
        suite = blessed_suite()
        assert suite.compare("cat food", (3, 1, 7)).verdict == "same"
        assert (
            suite.compare("cat food", (1, 3, 7)).verdict == "reordered"
        )
        assert suite.compare("cat food", (3, 1, 5)).verdict == "changed"

    def test_unblessed_queries_are_named(self):
        with pytest.raises(Missing):
            blessed_suite().compare("ghost", (1,))


class TestTheReleaseReport:
    def test_the_report_sorts_worst_first(self):
        suite = blessed_suite()
        report = suite.release_report(
            {
                "cat food": (3, 1, 5),
                "winter boots": (9, 2),
            }
        )
        lines = report.splitlines()
        assert lines[0] == "2 golden quer(ies), worst verdict: changed"
        assert lines[1].startswith("  CHANGED: 'cat food'")
        assert "this needs a review" in lines[1]
        assert lines[2] == "  same: 'winter boots'"

    def test_a_missing_observation_is_a_change(self):
        suite = blessed_suite()
        report = suite.release_report({"cat food": (3, 1, 7)})
        assert "CHANGED: 'winter boots'" in report

    def test_a_quiet_release_reads_same(self):
        suite = blessed_suite()
        report = suite.release_report(
            {"cat food": (3, 1, 7), "winter boots": (9, 2)}
        )
        assert "worst verdict: same" in report

    def test_an_empty_suite_guards_nothing(self):
        with pytest.raises(Invalid):
            GoldenSuite().release_report({})
