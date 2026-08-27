from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.ratelimit import Bucket, QueryGate


class TestBuckets:
    def test_the_burst_serves_the_bursty_afternoon(self):
        bucket = Bucket(rate=1.0, burst=3)
        assert [bucket.take(0) for _ in range(4)] == [
            True,
            True,
            True,
            False,
        ]

    def test_the_clock_refills_at_the_rate(self):
        bucket = Bucket(rate=0.5, burst=2)
        bucket.take(0)
        bucket.take(0)
        assert not bucket.take(1)
        assert bucket.take(2)

    def test_retry_after_is_arithmetic(self):
        bucket = Bucket(rate=0.5, burst=1)
        bucket.take(0)
        assert bucket.retry_after(0) == 2
        assert bucket.retry_after(2) == 0

    def test_zero_knobs_are_refused(self):
        with pytest.raises(Invalid):
            Bucket(rate=0.0, burst=1)


class TestTheGate:
    def test_separate_callers_hold_separate_buckets(self):
        gate = QueryGate(rate=1.0, burst=1)
        assert gate.admit("ada", now=0).allowed
        assert gate.admit("grace", now=0).allowed
        assert not gate.admit("ada", now=0).allowed

    def test_the_refusal_says_when_to_come_back(self):
        gate = QueryGate(rate=0.5, burst=1)
        gate.admit("ada", now=0)
        refusal = gate.admit("ada", now=0)
        assert not refusal.allowed
        assert refusal.retry_after == 2
        assert "retry in 2" in refusal.reason

    def test_anonymous_callers_are_refused(self):
        with pytest.raises(Invalid):
            QueryGate().admit("", now=0)


class TestTheLastStand:
    def test_the_ceiling_sheds_the_heaviest_first(self):
        gate = QueryGate(rate=100.0, burst=100, global_ceiling=5)
        for number in range(4):
            assert gate.admit("scraper", now=number).allowed
        assert gate.admit("ada", now=4).allowed
        refusal = gate.admit("scraper", now=5)
        assert not refusal.allowed
        assert "heaviest user" in refusal.reason
        assert gate.shed == 1

    def test_light_users_survive_the_ceiling(self):
        gate = QueryGate(rate=100.0, burst=100, global_ceiling=5)
        for number in range(5):
            gate.admit("scraper", now=number)
        assert gate.admit("ada", now=6).allowed

    def test_a_new_window_resets_the_stand(self):
        gate = QueryGate(rate=100.0, burst=100, global_ceiling=2)
        gate.admit("scraper", now=0)
        gate.admit("scraper", now=1)
        gate.new_window()
        assert gate.admit("scraper", now=2).allowed

    def test_the_pressure_report_names_the_heaviest(self):
        gate = QueryGate(rate=100.0, burst=100)
        for number in range(3):
            gate.admit("scraper", now=number)
        gate.admit("ada", now=3)
        report = gate.pressure()
        assert "heaviest caller scraper at 3 queries" in report
