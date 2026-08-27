from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.trending import Trend, TrendWatch


def two_windows() -> TrendWatch:
    watch = TrendWatch()
    for _ in range(4):
        watch.observe("weather")
    for _ in range(3):
        watch.observe("cat videos")
    for _ in range(8):
        watch.observe("election night")
    watch.roll_window()
    for _ in range(4):
        watch.observe("weather")
    for _ in range(9):
        watch.observe("cat videos")
    for _ in range(6):
        watch.observe("storm warning")
    watch.observe("election night")
    return watch


class TestRising:
    def test_the_riser_beats_its_own_yesterday(self):
        risers = two_windows().rising()
        assert len(risers) == 1
        assert risers[0].query == "cat videos"
        assert risers[0].ratio() == 3.0

    def test_flat_head_queries_are_not_news(self):
        risers = two_windows().rising()
        assert all(trend.query != "weather" for trend in risers)

    def test_the_volume_floor_blocks_the_fluke(self):
        watch = TrendWatch()
        watch.observe("obscure thing")
        watch.roll_window()
        for _ in range(3):
            watch.observe("obscure thing")
        assert watch.rising() == []


class TestNewborns:
    def test_something_from_nothing_is_its_own_section(self):
        newborns = two_windows().newborn()
        assert [trend.query for trend in newborns] == ["storm warning"]
        assert newborns[0].current == 6

    def test_a_newborn_ratio_is_refused_as_arithmetic(self):
        newborn = Trend(query="x", previous=0, current=6)
        with pytest.raises(Invalid, match=r"not\s+arithmetic"):
            newborn.ratio()

    def test_quiet_newborns_stay_out_of_the_paper(self):
        watch = TrendWatch()
        watch.roll_window()
        watch.observe("one-off")
        assert watch.newborn() == []


class TestFalling:
    def test_a_collapsing_head_query_is_an_outage_signal(self):
        fallers = two_windows().falling()
        assert [trend.query for trend in fallers] == ["election night"]
        assert fallers[0].previous == 8
        assert fallers[0].current == 1

    def test_small_yesterdays_cannot_collapse(self):
        watch = TrendWatch()
        watch.observe("tiny")
        watch.roll_window()
        assert watch.falling() == []


class TestTheDesk:
    def test_the_deskpage_reads_three_sections(self):
        page = two_windows().deskpage()
        assert "rising:" in page
        assert "cat videos: 3 -> 9 (3.0x)" in page
        assert "storm warning: 6 from nothing" in page
        assert "falling (check for outages):" in page

    def test_a_quiet_window_says_so(self):
        watch = TrendWatch()
        watch.roll_window()
        assert watch.deskpage() == "a quiet window; no news"

    def test_bad_knobs_are_refused(self):
        with pytest.raises(Invalid):
            TrendWatch(rise_factor=1.0)
        with pytest.raises(Invalid):
            TrendWatch(volume_floor=0)
        with pytest.raises(Invalid):
            TrendWatch().observe("  ")
