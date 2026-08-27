from __future__ import annotations

import pytest

from quarry.capacityplan import (
    fit_growth,
    forecast_crossing,
)
from quarry.errors import Invalid


class TestFitting:
    def test_a_clean_line_fits_exactly(self):
        fit = fit_growth([100, 200, 300, 400])
        assert fit.slope == 100.0
        assert fit.intercept == 100.0
        assert fit.level_at(5) == 600.0

    def test_noise_averages_out_instead_of_steering(self):
        fit = fit_growth([100, 210, 290, 400])
        assert 95.0 <= fit.slope <= 105.0

    def test_two_points_are_a_line_not_a_trend(self):
        with pytest.raises(Invalid, match="not a trend"):
            fit_growth([100, 200])

    def test_negative_counts_are_counting_bugs(self):
        with pytest.raises(Invalid, match="counting bug"):
            fit_growth([100, -5, 200])


class TestForecasting:
    def test_the_crossing_period_is_stated_with_working(self):
        held = forecast_crossing([100, 200, 300, 400], capacity=650)
        assert held.crossing_period == 6
        assert "3 period(s) from now" in held.verdict
        assert "headroom 250" in held.verdict
        assert not held.extrapolated

    def test_far_forecasts_are_labeled_extrapolation(self):
        held = forecast_crossing(
            [100, 110, 120], capacity=1000
        )
        assert held.extrapolated
        assert held.line().endswith("[extrapolation]")

    def test_shrinking_indexes_decline_to_predict(self):
        held = forecast_crossing([400, 300, 200], capacity=500)
        assert held.crossing_period is None
        assert "shrinking" in held.verdict

    def test_already_over_says_so_without_arithmetic(self):
        held = forecast_crossing([100, 300, 700], capacity=600)
        assert held.verdict.startswith("already over: 700 of 600")

    def test_a_flat_index_never_crosses(self):
        held = forecast_crossing([200, 200, 200], capacity=900)
        assert held.crossing_period is None

    def test_zero_capacity_is_already_crossed(self):
        with pytest.raises(Invalid, match="already crossed"):
            forecast_crossing([1, 2, 3], capacity=0)
