from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.sparkline import labeled, spark


class TestShapes:
    def test_rise_and_fall_read_at_a_glance(self):
        line = spark([0, 3, 6, 3, 0])
        assert line.startswith(".=#=.")
        assert line.endswith("(0 to 6)")

    def test_the_bounds_ride_with_the_line(self):
        assert "(10 to 90)" in spark([10, 50, 90])

    def test_a_flat_series_says_flat(self):
        line = spark([5, 5, 5])
        assert line == "... (flat at 5)"

    def test_missing_points_are_gaps_not_zeros(self):
        line = spark([0, None, 6])
        assert line.startswith(". #")

    def test_extremes_use_the_whole_ramp(self):
        line = spark([1, 100])
        assert line.startswith(".#")


class TestRefusals:
    def test_nothing_draws_nothing(self):
        with pytest.raises(Invalid, match="draws nothing"):
            spark([])

    def test_an_all_missing_week_is_named(self):
        with pytest.raises(Invalid, match="down all week"):
            spark([None, None])

    def test_labels_are_mandatory(self):
        with pytest.raises(Invalid, match="decorates nothing"):
            labeled("  ", [1, 2])


class TestLabeling:
    def test_the_label_leads_the_line(self):
        line = labeled("p95_ms", [80, 80, 200])
        assert line.startswith("p95_ms: ")
        assert "(80 to 200)" in line
