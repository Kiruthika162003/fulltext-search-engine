from __future__ import annotations

import pytest

from quarry.bloom import BloomFilter
from quarry.errors import Frozen, Invalid


def loaded() -> BloomFilter:
    held = BloomFilter(capacity=200, target_rate=0.01)
    for n in range(200):
        held.add(f"doc-{n}")
    return held


class TestTheContract:
    def test_absence_is_certain(self):
        held = BloomFilter(capacity=10, target_rate=0.01)
        held.add("doc-1")
        assert not held.maybe_contains("never-seen")

    def test_presence_is_never_lost(self):
        held = loaded()
        assert all(
            held.maybe_contains(f"doc-{n}") for n in range(200)
        )

    def test_the_measured_rate_honors_the_target(self):
        held = loaded()
        assert held.measured_rate() <= 0.02
        assert "inside its promise" in held.contract_page()

    def test_sizing_follows_the_formulas(self):
        held = BloomFilter(capacity=200, target_rate=0.01)
        assert held.bits >= 1900
        assert 5 <= held.hashes <= 9


class TestRefusals:
    def test_overfilling_answers_probably_to_everything(self):
        held = BloomFilter(capacity=2, target_rate=0.01)
        held.add("a")
        held.add("b")
        with pytest.raises(Frozen, match="refuses instead"):
            held.add("c")

    def test_silly_rates_are_a_coin(self):
        with pytest.raises(Invalid, match="flip a coin"):
            BloomFilter(capacity=10, target_rate=0.9)

    def test_empty_capacity_filters_nothing(self):
        with pytest.raises(Invalid, match="filters nothing"):
            BloomFilter(capacity=0, target_rate=0.01)

    def test_probeless_measurement_measures_nothing(self):
        with pytest.raises(Invalid, match="measures nothing"):
            loaded().measured_rate(probes=0)
