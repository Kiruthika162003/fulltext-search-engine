from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.kpiweekly import WeekNumbers, digest, story


def week(label: str, **overrides: float) -> WeekNumbers:
    values = {
        "queries_served": 10000.0,
        "zero_result_share": 0.10,
        "click_through_share": 0.40,
        "p95_latency_ms": 80.0,
        "freshness_lag_min": 20.0,
    }
    values.update(overrides)
    return WeekNumbers(label=label, values=values)


class TestTheNumbers:
    def test_missing_metrics_are_the_oldest_trick(self):
        with pytest.raises(Missing, match="oldest trick"):
            WeekNumbers(
                label="w2",
                values={"queries_served": 100.0},
            )

    def test_stray_metrics_are_refused(self):
        with pytest.raises(Invalid, match="five numbers"):
            week("w1").values
            WeekNumbers(
                label="w1",
                values={
                    **week("w1").values,
                    "vibes": 10.0,
                },
            )


class TestTheDigest:
    def test_wiggles_inside_the_bands_are_weather(self):
        page = digest(
            week("w1"), week("w2", click_through_share=0.406)
        )
        assert "click_through_share: 0.406 (was 0.4, steady)" in page
        assert "nothing moved outside the bands" in page

    def test_directions_respect_lower_is_better(self):
        page = digest(
            week("w1"),
            week("w2", p95_latency_ms=60.0, queries_served=12000.0),
        )
        assert "p95_latency_ms: 60.0 (was 80.0, better)" in page
        assert "queries_served: 12000.0 (was 10000.0, better)" in page
        assert "movements: queries_served better; p95_latency_ms better" in page

    def test_worsening_is_named_without_adjectives(self):
        page = digest(
            week("w1"), week("w2", zero_result_share=0.2)
        )
        assert "zero_result_share: 0.2 (was 0.1, worse)" in page

    def test_a_week_cannot_compare_to_itself(self):
        with pytest.raises(Invalid, match="always reads steady"):
            digest(week("w1"), week("w1"))


class TestTheStory:
    def test_weeks_chain_into_a_story(self):
        page = story(
            [
                week("w1"),
                week("w2", p95_latency_ms=60.0),
                week("w3", p95_latency_ms=90.0),
            ]
        )
        assert "week w2 (vs w1):" in page
        assert "week w3 (vs w2):" in page

    def test_one_week_is_a_snapshot(self):
        with pytest.raises(Invalid, match="snapshot"):
            story([week("w1")])
