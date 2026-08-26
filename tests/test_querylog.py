from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.querylog import QueryLog


def busy_day() -> QueryLog:
    log = QueryLog()
    for number in range(4):
        log.log(f"s{number}", "cat food", results=12, clicked=True)
    log.log("s0", "dog beds", results=8, clicked=False)
    for number in range(3):
        log.log(f"r{number}", "cheap flights", results=0, clicked=False)
        log.log(f"r{number}", "budget airlines", results=9, clicked=True)
    log.log("s9", "xylophone lessons", results=0, clicked=False)
    return log


class TestLogging:
    def test_a_click_on_nothing_is_a_contradiction(self):
        with pytest.raises(Invalid, match="instrumentation"):
            QueryLog().log("s", "cat", results=0, clicked=True)

    def test_blank_rows_are_refused(self):
        with pytest.raises(Invalid):
            QueryLog().log("", "cat", results=1, clicked=False)
        with pytest.raises(Invalid):
            QueryLog().log("s", "  ", results=1, clicked=False)

    def test_negative_counts_blame_upstream(self):
        with pytest.raises(Invalid, match="upstream"):
            QueryLog().log("s", "cat", results=-1, clicked=False)


class TestReadings:
    def test_top_queries_rank_by_volume(self):
        top = busy_day().top_queries(limit=2)
        assert top[0] == ("cat food", 4)
        assert top[1][1] == 3

    def test_the_wall_ranks_the_zero_result_pain(self):
        wall = busy_day().zero_result_wall(limit=2)
        assert wall[0] == ("cheap flights", 3)
        assert wall[1] == ("xylophone lessons", 1)

    def test_abandonment_counts_only_served_queries(self):
        rate = busy_day().abandonment_rate()
        assert rate == pytest.approx(1 / 8)

    def test_an_empty_log_refuses_the_rate(self):
        with pytest.raises(Invalid, match="nothing to abandon"):
            QueryLog().abandonment_rate()


class TestReformulations:
    def test_the_give_up_and_retry_pair_is_mined(self):
        pairs = busy_day().reformulations()
        assert pairs[("cheap flights", "budget airlines")] == 3

    def test_candidates_need_the_floor(self):
        log = busy_day()
        log.log("lone", "cheap flights", results=0, clicked=False)
        log.log("lone", "discount carriers", results=5, clicked=True)
        candidates = log.synonym_candidates(floor=3)
        assert candidates == [("cheap flights", "budget airlines", 3)]

    def test_a_floor_of_one_is_refused_as_anecdote(self):
        with pytest.raises(Invalid, match="anecdotes"):
            busy_day().synonym_candidates(floor=1)

    def test_successful_first_tries_are_not_reformulations(self):
        log = QueryLog()
        log.log("s", "cat", results=5, clicked=False)
        log.log("s", "cat food", results=5, clicked=True)
        assert log.reformulations() == {}


class TestBriefing:
    def test_the_briefing_reads_wall_then_candidates(self):
        page = busy_day().briefing()
        assert page.splitlines()[0] == "12 queries logged"
        assert "the wall: cheap flights (3)" in page
        assert (
            "synonym candidate: 'cheap flights' -> 'budget airlines', "
            "3 sessions agree" in page
        )
