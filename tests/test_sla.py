from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid
from quarry.sla import Objective, SloTracker


def latency_slo() -> SloTracker:
    return SloTracker(
        objective=Objective(
            name="search-fast",
            target_share=0.95,
            latency_ceiling=100,
        ),
        window_size=100,
    )


class TestObjectives:
    def test_promising_everything_is_not_an_objective(self):
        with pytest.raises(Invalid, match="not an objective"):
            Objective(name="perfect", target_share=1.0)

    def test_the_budget_is_the_complement(self):
        held = Objective(name="ok", target_share=0.99)
        assert held.budget_share() == 0.01

    def test_thin_windows_cannot_hold_verdicts(self):
        with pytest.raises(Invalid, match="floor"):
            SloTracker(
                objective=Objective(name="ok", target_share=0.9),
                window_size=5,
            )


class TestObservation:
    def test_slow_successes_are_bad_under_a_ceiling(self):
        tracker = latency_slo()
        tracker.observe(ok=True, latency=250)
        assert tracker.bad == 1

    def test_latency_is_mandatory_when_the_ceiling_exists(self):
        with pytest.raises(Invalid, match="cannot be judged"):
            latency_slo().observe(ok=True)

    def test_failures_never_need_latency(self):
        tracker = latency_slo()
        tracker.observe(ok=False)
        assert tracker.bad == 1


class TestBudgetArithmetic:
    def test_the_budget_spends_per_bad_request(self):
        tracker = latency_slo()
        for _ in range(18):
            tracker.observe(ok=True, latency=50)
        tracker.observe(ok=False)
        tracker.observe(ok=False)
        assert tracker.budget_total() == 5.0
        assert tracker.budget_spent_share() == 0.4

    def test_burn_rate_compares_spend_to_time(self):
        tracker = latency_slo()
        for _ in range(18):
            tracker.observe(ok=True, latency=50)
        tracker.observe(ok=False)
        tracker.observe(ok=False)
        assert tracker.burn_rate() == 2.0
        assert not tracker.alerting()

    def test_alerts_fire_above_double_burn(self):
        tracker = latency_slo()
        for _ in range(17):
            tracker.observe(ok=True, latency=50)
        for _ in range(3):
            tracker.observe(ok=False)
        assert tracker.alerting()


class TestGoalposts:
    def test_the_target_does_not_move_mid_window(self):
        with pytest.raises(Frozen, match="goalposts"):
            latency_slo().retarget(0.9)

    def test_sealed_windows_take_no_backfill(self):
        tracker = latency_slo()
        tracker.close()
        with pytest.raises(Frozen, match="sealed"):
            tracker.observe(ok=True, latency=10)


class TestReporting:
    def test_thin_evidence_reports_no_verdict(self):
        tracker = latency_slo()
        tracker.observe(ok=True, latency=10)
        assert "observations needed" in tracker.report()

    def test_the_verdict_carries_the_sample_count(self):
        tracker = latency_slo()
        for _ in range(20):
            tracker.observe(ok=True, latency=50)
        page = tracker.report()
        assert "n=20" in page
        assert "within budget" in page

    def test_a_breached_close_is_recorded(self):
        tracker = latency_slo()
        for _ in range(14):
            tracker.observe(ok=True, latency=50)
        for _ in range(6):
            tracker.observe(ok=False)
        tracker.close()
        assert tracker.breaches == ["window closed breached at 120%"]
