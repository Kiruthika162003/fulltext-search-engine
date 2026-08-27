from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.reservoir import (
    Reservoir,
    fairness_check,
    same_sample_any_order,
)

KEYS = [f"doc-{n}" for n in range(200)]


class TestSampling:
    def test_the_reservoir_holds_its_size(self):
        held = Reservoir(purpose="audit", size=10)
        for key in KEYS:
            held.offer(key)
        assert len(held.sample()) == 10
        assert held.seen == 200

    def test_arrival_order_does_not_matter(self):
        assert same_sample_any_order("audit", 10, KEYS)

    def test_the_same_purpose_replays_the_same_sample(self):
        left = Reservoir(purpose="audit", size=10)
        right = Reservoir(purpose="audit", size=10)
        for key in KEYS:
            left.offer(key)
            right.offer(key)
        assert left.sample() == right.sample()

    def test_distinct_purposes_draw_distinct_samples(self):
        fraud = Reservoir(purpose="fraud", size=10)
        quality = Reservoir(purpose="quality", size=10)
        for key in KEYS:
            fraud.offer(key)
            quality.offer(key)
        assert fraud.sample() != quality.sample()

    def test_double_offers_double_the_odds(self):
        held = Reservoir(purpose="audit", size=5)
        held.offer("doc-1")
        with pytest.raises(Invalid, match="double its odds"):
            held.offer("doc-1")


class TestContracts:
    def test_purposeless_samples_share_blind_spots(self):
        with pytest.raises(Invalid, match="name it"):
            Reservoir(purpose=" ", size=5)

    def test_zero_reservoirs_audit_nothing(self):
        with pytest.raises(Invalid, match="audits nothing"):
            Reservoir(purpose="audit", size=0)

    def test_the_line_states_the_arithmetic(self):
        held = Reservoir(purpose="audit", size=3)
        for key in KEYS[:7]:
            held.offer(key)
        assert held.line() == (
            "audit: 3 of 7 seen, deterministic by purpose"
        )


class TestFairness:
    def test_inclusion_odds_land_near_the_ratio(self):
        share = fairness_check(
            size=10, stream_length=50, trials=60
        )
        assert 0.08 <= share <= 0.35

    def test_fairness_needs_a_real_stream(self):
        with pytest.raises(Invalid, match="at least as long"):
            fairness_check(size=10, stream_length=5, trials=3)
