from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.slowlog import SlowLog


def a_day() -> SlowLog:
    log = SlowLog(slow_line=100)
    for _ in range(96):
        log.observe("body:cat", took=2)
    log.observe("marketing monday", took=900, terms=11, candidates=5000,
                segments=4)
    log.observe("marketing monday", took=700, terms=11, candidates=4800,
                segments=4)
    log.observe("one whale", took=2000, terms=2, candidates=90000,
                segments=4)
    log.observe("body:dog", took=40)
    return log


class TestObservation:
    def test_fast_queries_pass_unlogged_but_counted(self):
        log = SlowLog(slow_line=100)
        assert not log.observe("q", took=5)
        assert log.entries == []
        assert log.all_timings == [5]

    def test_slow_queries_keep_their_anatomy(self):
        log = SlowLog(slow_line=100)
        assert log.observe("q", took=500, terms=3, candidates=100, segments=2)
        assert log.entries[0].candidates == 100

    def test_negative_timings_blame_the_clock(self):
        with pytest.raises(Invalid, match="clock skew"):
            SlowLog().observe("q", took=-1)

    def test_a_zero_line_is_refused(self):
        with pytest.raises(Invalid):
            SlowLog(slow_line=0)


class TestThePopulation:
    def test_percentiles_come_from_everyone(self):
        log = a_day()
        assert log.percentile(0.5) == 2
        assert log.percentile(0.99) >= 700

    def test_the_slow_share_is_a_fraction_of_all(self):
        assert a_day().slow_share() == 0.03

    def test_empty_logs_refuse_percentiles(self):
        with pytest.raises(Invalid):
            SlowLog().percentile(0.5)


class TestOffenders:
    def test_habitual_offenders_group_by_canonical_query(self):
        offenders = a_day().repeat_offenders()
        assert offenders == [("marketing monday", 2, 900)]

    def test_one_slow_run_is_an_incident_not_a_habit(self):
        offenders = a_day().repeat_offenders()
        assert all(name != "one whale" for name, _, _ in offenders)
        with pytest.raises(Invalid, match="incident"):
            a_day().repeat_offenders(floor=1)

    def test_the_worst_anatomy_is_spelled_out(self):
        anatomy = a_day().anatomy_of_the_worst()
        assert anatomy == (
            "one whale: 2000 ticks, 2 terms, 90000 candidates across "
            "4 segment(s)"
        )

    def test_a_quiet_log_says_the_line_holds(self):
        assert SlowLog().anatomy_of_the_worst() == (
            "nothing slow yet; the line holds"
        )


class TestReport:
    def test_the_report_reads_population_then_habits(self):
        page = a_day().report()
        assert page.startswith("100 queries, p50 2")
        assert "3.0% past the line" in page
        assert "habitual: marketing monday slow 2 times, worst 900" in page
