from __future__ import annotations

import pytest

from quarry.distinctcount import DistinctCounter, merged
from quarry.errors import Invalid


def fed(count: int, prefix: str = "q") -> DistinctCounter:
    held = DistinctCounter()
    for n in range(count):
        held.observe(f"{prefix}-{n}")
    return held


class TestSmallCounts:
    def test_small_sets_count_exactly(self):
        value, words = fed(40).estimate()
        assert value == 40
        assert "exact" in words
        assert "embarrassing" in words

    def test_repeats_never_inflate(self):
        held = DistinctCounter()
        for _ in range(5):
            held.observe("same-query")
        value, _ = held.estimate()
        assert value == 1

    def test_nobody_is_refused(self):
        with pytest.raises(Invalid, match="nobody"):
            DistinctCounter().observe("")


class TestSketchedCounts:
    def test_large_counts_land_inside_the_error(self):
        value, words = fed(5000).estimate()
        assert "registers" in words
        assert 4000 <= value <= 6000

    def test_the_estimate_confesses_its_error(self):
        _, words = fed(5000).estimate()
        assert "+/- 13%" in words


class TestMerging:
    def test_shards_count_together_without_sharing_sets(self):
        left = fed(3000, prefix="left")
        right = fed(3000, prefix="right")
        combined, _ = merged([left, right]).estimate()
        assert 4500 <= combined <= 7500

    def test_merging_overlapping_shards_never_doubles(self):
        left = fed(3000)
        right = fed(3000)
        combined, _ = merged([left, right]).estimate()
        solo, _ = left.estimate()
        assert abs(combined - solo) <= solo * 0.02

    def test_merging_nothing_counts_nothing(self):
        with pytest.raises(Invalid, match="counts nothing"):
            merged([])
