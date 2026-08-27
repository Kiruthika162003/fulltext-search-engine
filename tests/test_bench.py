from __future__ import annotations

import pytest

from quarry.bench import BenchResult, compare, measure
from quarry.errors import Invalid


class TestMeasurement:
    def test_the_result_carries_median_and_spread(self):
        result = measure("noop", lambda: None, runs=9, warmup=1)
        assert result.runs == 9
        assert result.median_us >= 0.0
        assert result.spread >= 1.0

    def test_warmup_runs_are_executed_and_discarded(self):
        calls = []
        measure("counted", lambda: calls.append(1), runs=5, warmup=3)
        assert len(calls) == 8

    def test_too_few_runs_cannot_be_quoted(self):
        with pytest.raises(Invalid, match="five is the floor"):
            measure("thin", lambda: None, runs=2)

    def test_warmup_is_mandatory(self):
        with pytest.raises(Invalid, match="steady state"):
            measure("cold", lambda: None, runs=5, warmup=0)


def result(label: str, median: float, spread: float = 1.5, runs: int = 30):
    return BenchResult(
        label=label, runs=runs, median_us=median, spread=spread
    )


class TestComparison:
    def test_a_clear_winner_is_a_ratio(self):
        page = compare(result("old", 100.0), result("new", 40.0))
        assert page == (
            "new is 2.5x faster than old (40.0us vs 100.0us)"
        )

    def test_the_noise_band_refuses_a_winner(self):
        page = compare(result("a", 100.0), result("b", 95.0))
        assert page.startswith("no winner")

    def test_noisy_results_are_not_quotable(self):
        page = compare(
            result("old", 100.0, spread=8.0),
            result("new", 40.0),
        )
        assert "rerun before quoting" in page

    def test_unequal_efforts_flatter_the_lazy(self):
        with pytest.raises(Invalid, match="flatters"):
            compare(
                result("a", 100.0, runs=30),
                result("b", 40.0, runs=10),
            )


class TestStability:
    def test_the_line_names_noise(self):
        assert "NOISY" in result("x", 10.0, spread=5.0).line()
        assert "stable" in result("x", 10.0, spread=1.2).line()
