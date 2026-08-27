from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.noisycounts import (
    GRAIN,
    publish,
    stable_across_reads,
)

COUNTS = {
    "kettle": 1042,
    "stove": 388,
    "rare-illness": 3,
    "one-person": 1,
}


class TestSuppression:
    def test_small_crowds_are_withheld_by_name(self):
        report = publish(COUNTS, "2026-08")
        assert "rare-illness" not in report.published
        assert "one-person" not in report.published
        assert report.suppressed_terms == 2

    def test_the_arithmetic_still_closes(self):
        report = publish(COUNTS, "2026-08")
        assert report.suppressed_total in (0, GRAIN)

    def test_the_page_says_what_it_withheld(self):
        page = publish(COUNTS, "2026-08").page("2026-08")
        assert "2 term(s)" in page
        assert "names withheld" in page
        assert "crowds under 10 withheld" in page


class TestRounding:
    def test_published_counts_sit_on_the_grain(self):
        report = publish(COUNTS, "2026-08")
        assert all(
            count % GRAIN == 0
            for count in report.published.values()
        )

    def test_counts_stay_near_the_truth(self):
        report = publish(COUNTS, "2026-08")
        assert abs(report.published["kettle"] - 1042) <= GRAIN
        assert abs(report.published["stove"] - 388) <= GRAIN


class TestDeterminism:
    def test_the_second_look_leaks_nothing_new(self):
        assert stable_across_reads(COUNTS, "2026-08")

    def test_different_periods_jitter_differently(self):
        july = publish(COUNTS, "2026-07").published
        august = publish(COUNTS, "2026-08").published
        assert july.keys() == august.keys()

    def test_stability_needs_two_reads(self):
        with pytest.raises(Invalid, match="two reads"):
            stable_across_reads(COUNTS, "2026-08", reads=1)


class TestRefusals:
    def test_negative_counts_are_bugs(self):
        with pytest.raises(Invalid, match="counting bug"):
            publish({"x": -1}, "2026-08")

    def test_nameless_periods_cannot_be_retracted(self):
        with pytest.raises(Invalid, match="name it"):
            publish(COUNTS, "  ")
