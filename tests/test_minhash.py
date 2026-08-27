from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.minhash import (
    calibration_report,
    sketch,
    true_jaccard,
)

KETTLE_PAGE = {f"term-{n}" for n in range(40)}
NEAR_TWIN = {f"term-{n}" for n in range(4, 44)}
STRANGER = {f"other-{n}" for n in range(40)}


class TestSketching:
    def test_identical_sets_agree_completely(self):
        left = sketch(KETTLE_PAGE)
        right = sketch(KETTLE_PAGE)
        assert left.agreement(right) == 1.0

    def test_strangers_barely_agree(self):
        agreement = sketch(KETTLE_PAGE).agreement(sketch(STRANGER))
        assert agreement <= 0.1

    def test_twins_land_near_their_true_jaccard(self):
        truth = true_jaccard(KETTLE_PAGE, NEAR_TWIN)
        estimate = sketch(KETTLE_PAGE, 256).agreement(
            sketch(NEAR_TWIN, 256)
        )
        assert abs(estimate - truth) <= 0.125

    def test_widths_must_match(self):
        with pytest.raises(Invalid, match="numerology"):
            sketch(KETTLE_PAGE, 16).agreement(
                sketch(KETTLE_PAGE, 32)
            )

    def test_empty_sets_claim_everything(self):
        with pytest.raises(Invalid, match="everything"):
            sketch(set())

    def test_thin_widths_confess_too_much(self):
        with pytest.raises(Invalid, match="sixteen is the floor"):
            sketch(KETTLE_PAGE, 8)


class TestHonestNumbers:
    def test_the_error_rides_with_the_estimate(self):
        held = sketch(KETTLE_PAGE, 16)
        assert held.standard_error() == 0.25
        line = held.estimate_line(sketch(NEAR_TWIN, 16))
        assert "+/- 0.25" in line
        assert "not a\nmeasurement" in line or "not a measurement" in line

    def test_the_calibration_stays_inside_its_bound(self):
        page = calibration_report(KETTLE_PAGE, NEAR_TWIN, 256)
        assert "inside two standard errors" in page

    def test_jaccard_of_nothing_is_undefined(self):
        with pytest.raises(Invalid, match="undefined"):
            true_jaccard(set(), set())
