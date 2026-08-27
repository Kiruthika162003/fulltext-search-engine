from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.quantiles import QuantileSketch, merged


def loaded() -> QuantileSketch:
    sketch = QuantileSketch()
    for value in [3] * 50 + [15] * 40 + [80] * 9 + [400]:
        sketch.observe(value)
    return sketch


class TestObservation:
    def test_values_land_in_their_buckets(self):
        sketch = QuantileSketch()
        sketch.observe(3)
        sketch.observe(15)
        sketch.observe(9999)
        assert sketch.counts[2] == 1
        assert sketch.counts[4] == 1
        assert sketch.overflow() == 1

    def test_negative_latency_is_a_clock_bug(self):
        with pytest.raises(Invalid, match="clock bug"):
            QuantileSketch().observe(-1)


class TestQuantiles:
    def test_the_median_lands_where_the_mass_is(self):
        value, described = loaded().quantile(0.5)
        assert value == 5
        assert "(2, 5]" in described

    def test_the_p95_reads_the_tail(self):
        value, described = loaded().quantile(0.95)
        assert value == 100
        assert "resolution" in described

    def test_the_ends_are_refused_by_name(self):
        with pytest.raises(Invalid, match="min and max"):
            loaded().quantile(1.0)

    def test_empty_sketches_produce_fiction(self):
        with pytest.raises(Invalid, match="fiction"):
            QuantileSketch().quantile(0.5)

    def test_an_overflowing_quantile_says_beyond_the_scale(self):
        sketch = QuantileSketch()
        for _ in range(10):
            sketch.observe(99999)
        _, described = sketch.quantile(0.5)
        assert "BEYOND THE SCALE" in described


class TestTheReport:
    def test_the_report_carries_resolutions_and_n(self):
        page = loaded().report()
        assert "p50%" in page
        assert "n=100" in page

    def test_overflow_is_reported_never_hidden(self):
        sketch = loaded()
        for _ in range(9):
            sketch.observe(99999)
        page = sketch.report()
        assert "OVERFLOW: 9 observation(s) (8.3%)" in page
        assert "no longer exists" in page


class TestMerging:
    def test_shard_sketches_merge_by_addition(self):
        left = QuantileSketch()
        right = QuantileSketch()
        for _ in range(50):
            left.observe(3)
            right.observe(80)
        combined = merged([left, right])
        assert combined.total == 100
        value, _ = combined.quantile(0.5)
        assert value == 5

    def test_merging_nothing_makes_nothing(self):
        with pytest.raises(Invalid, match="no sketch"):
            merged([])
