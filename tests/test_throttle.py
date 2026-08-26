from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.throttle import IndexThrottle


def loaded(count: int = 50) -> IndexThrottle:
    throttle = IndexThrottle(
        capacity=100, guaranteed=5, backlog_limit=60
    )
    for number in range(count):
        throttle.offer(f"doc-{number}")
    return throttle


class TestAdmission:
    def test_a_quiet_engine_grants_generously(self):
        throttle = loaded()
        granted = throttle.tick(query_busy_share=0.0)
        assert len(granted) == 50
        assert throttle.depth() == 0

    def test_a_busy_engine_grants_the_leftovers(self):
        throttle = loaded()
        granted = throttle.tick(query_busy_share=0.8)
        assert len(granted) == 20
        assert throttle.depth() == 30

    def test_full_load_still_grants_the_guarantee(self):
        throttle = loaded()
        granted = throttle.tick(query_busy_share=1.0)
        assert len(granted) == 5

    def test_grants_preserve_arrival_order(self):
        throttle = loaded(count=10)
        granted = throttle.tick(query_busy_share=0.95)
        assert granted == [f"doc-{n}" for n in range(5)]


class TestTheBacklog:
    def test_overflow_rejects_at_the_front_door(self):
        throttle = loaded(count=60)
        assert not throttle.offer("doc-60")
        assert throttle.rejected_at_the_door == 1
        assert throttle.depth() == 60

    def test_nothing_is_dropped_from_the_middle(self):
        throttle = loaded(count=60)
        throttle.offer("doc-60")
        drained = []
        while throttle.depth():
            drained.extend(throttle.tick(query_busy_share=0.9))
        assert drained == [f"doc-{n}" for n in range(60)]

    def test_the_drain_estimate_is_ceiling_arithmetic(self):
        throttle = loaded(count=50)
        assert throttle.drain_estimate(query_busy_share=0.8) == 3
        assert throttle.drain_estimate(query_busy_share=1.0) == 10
        throttle.tick(query_busy_share=0.0)
        assert throttle.drain_estimate(query_busy_share=0.0) == 0


class TestContracts:
    def test_busyness_is_a_fraction(self):
        with pytest.raises(Invalid):
            loaded().tick(query_busy_share=1.5)

    def test_a_guarantee_of_zero_starves_the_indexer(self):
        with pytest.raises(Invalid, match="starves"):
            IndexThrottle(capacity=100, guaranteed=0)

    def test_the_pressure_report_reads_the_door(self):
        throttle = loaded(count=60)
        throttle.offer("doc-60")
        report = throttle.pressure_report()
        assert report == (
            "backlog 60/60, 0 admitted, 1 rejected at the door"
        )
