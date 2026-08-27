from __future__ import annotations

import dataclasses

import pytest

from quarry.backpressure import Backpressure
from quarry.chaosdrill import Drill, DrillBook
from quarry.errors import Frozen, Invalid
from quarry.journal import Journal


def replica_loss_scenario() -> str:
    survivors = ["shard-b", "shard-c"]
    if not survivors:
        raise RuntimeError("no shards left to answer")
    return f"answered from {len(survivors)} survivor(s)"


def corrupt_tail_scenario() -> str:
    journal = Journal()
    journal.append("add", "doc:0 fine")
    journal.append("add", "doc:1 doomed")
    journal.entries[1] = dataclasses.replace(
        journal.entries[1], payload="doc:1 edited"
    )
    kept, verdict = journal.replay()
    if not verdict.startswith("REPLAY STOPPED"):
        raise RuntimeError("corruption imported silently")
    return f"replay kept {len(kept)} and stopped loudly"


def buffer_flood_scenario() -> str:
    pressure = Backpressure(capacity=20)
    for _ in range(18):
        pressure.admit(urgent=True)
    pressure.admit()
    raise RuntimeError("black stage admitted casual traffic")


class TestSingleDrills:
    def test_a_surviving_scenario_says_how(self):
        result = Drill("replica-loss", replica_loss_scenario).run()
        assert result.verdict == "survived"
        assert "2 survivor(s)" in result.evidence

    def test_a_loud_refusal_is_degradation_by_design(self):
        result = Drill("buffer-flood", buffer_flood_scenario).run()
        assert result.verdict == "degraded as designed"
        assert "refused loudly" in result.evidence

    def test_a_crash_is_a_failed_drill(self):
        def dies() -> str:
            raise ZeroDivisionError("division by zero")

        result = Drill("bad-arithmetic", dies).run()
        assert result.verdict == "FAILED DRILL"
        assert "ZeroDivisionError" in result.evidence

    def test_the_corrupt_tail_drill_survives_on_loud_replay(self):
        result = Drill("corrupt-tail", corrupt_tail_scenario).run()
        assert result.verdict == "survived"
        assert "stopped loudly" in result.evidence


class TestTheBook:
    def full_book(self) -> DrillBook:
        book = DrillBook()
        book.schedule(Drill("replica-loss", replica_loss_scenario))
        book.schedule(Drill("corrupt-tail", corrupt_tail_scenario))
        book.schedule(Drill("buffer-flood", buffer_flood_scenario))
        return book

    def test_duplicate_names_hide_verdicts(self):
        book = self.full_book()
        with pytest.raises(Invalid, match="hides one of them"):
            book.schedule(
                Drill("replica-loss", replica_loss_scenario)
            )

    def test_an_empty_book_certifies_nothing(self):
        with pytest.raises(Invalid, match="certifies nothing"):
            DrillBook().run_all()

    def test_a_clean_run_reports_rehearsed_not_imagined(self):
        book = self.full_book()
        book.run_all()
        page = book.report()
        assert "all 3 drills held" in page
        assert "rehearsed, not imagined" in page

    def test_failures_are_counted_and_shouted(self):
        book = DrillBook()

        def dies() -> str:
            raise RuntimeError("boom")

        book.schedule(Drill("doomed", dies))
        book.run_all()
        assert "1 of 1 drills FAILED" in book.report()


class TestScenarioHonesty:
    def test_the_flood_scenario_would_catch_a_soft_gate(self):
        with pytest.raises(Frozen):
            pressure = Backpressure(capacity=20)
            for _ in range(18):
                pressure.admit(urgent=True)
            pressure.admit()
