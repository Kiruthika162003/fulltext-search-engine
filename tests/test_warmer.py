from __future__ import annotations

import pytest

from quarry.engine import Engine
from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.warmer import CacheWarmer


def engine() -> Engine:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    built = Engine(schema=schema)
    built.add({"body": "the black cat"})
    built.add({"body": "a friendly dog"})
    built.commit()
    return built


def volumes() -> dict[str, int]:
    return {"cat": 700, "dog": 200, "weather": 90, "niche": 10}


class TestWarming:
    def test_the_head_replays_within_the_budget(self):
        warmer = CacheWarmer(engine=engine(), budget=2)
        report = warmer.warm(volumes())
        assert report.replayed == ("cat", "dog")

    def test_coverage_is_volume_not_query_count(self):
        warmer = CacheWarmer(engine=engine(), budget=2)
        report = warmer.warm(volumes())
        assert report.coverage() == 0.9
        assert report.morning_note().startswith(
            "warmed 2 queries covering 90%"
        )

    def test_a_broken_query_is_reported_and_skipped(self):
        warmer = CacheWarmer(engine=engine(), budget=2)
        report = warmer.warm({"cat": 700, '"unclosed': 300})
        assert report.replayed == ("cat",)
        assert len(report.failed) == 1
        assert "BROKEN during warming" in report.morning_note()

    def test_failed_volume_never_counts_as_covered(self):
        warmer = CacheWarmer(engine=engine(), budget=2)
        report = warmer.warm({"cat": 700, '"unclosed': 300})
        assert report.volume_covered == 700
        assert report.coverage() == 0.7


class TestContracts:
    def test_a_zero_budget_is_a_cold_cache_with_a_plan(self):
        with pytest.raises(Invalid, match="with a plan"):
            CacheWarmer(engine=engine(), budget=0)

    def test_an_empty_log_warms_nothing_honestly(self):
        with pytest.raises(Invalid, match="run cold honestly"):
            CacheWarmer(engine=engine()).warm({})
