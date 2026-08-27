from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.tiered import TierLedger


def aging_fleet() -> TierLedger:
    ledger = TierLedger()
    ledger.admit("seg-new", sealed_at=100)
    ledger.admit("seg-mid", sealed_at=60)
    ledger.admit("seg-old", sealed_at=0)
    return ledger


class TestThePolicy:
    def test_age_demotes_step_by_step(self):
        ledger = aging_fleet()
        acted = ledger.settle(now=100)
        assert ledger.tier_of("seg-new") == "hot"
        assert ledger.tier_of("seg-mid") == "warm"
        assert ledger.tier_of("seg-old") == "warm"
        assert len(acted) == 2
        acted = ledger.settle(now=100)
        assert ledger.tier_of("seg-old") == "cold"
        assert len(acted) == 1

    def test_heat_promotes_from_any_seat(self):
        ledger = aging_fleet()
        ledger.settle(now=100)
        ledger.settle(now=100)
        for _ in range(10):
            ledger.touched("seg-old")
        ledger.settle(now=101)
        assert ledger.tier_of("seg-old") == "hot"

    def test_mild_heat_does_not_promote(self):
        ledger = aging_fleet()
        ledger.settle(now=100)
        for _ in range(3):
            ledger.touched("seg-mid")
        ledger.settle(now=101)
        assert ledger.tier_of("seg-mid") == "warm"

    def test_mild_heat_does_not_stop_the_slide(self):
        ledger = aging_fleet()
        for _ in range(6):
            ledger.touched("seg-old")
        ledger.settle(now=100)
        for _ in range(6):
            ledger.touched("seg-old")
        ledger.settle(now=101)
        assert ledger.tier_of("seg-old") == "cold"
        assert ledger.rows["seg-old"].recent_queries == 0


class TestTheLedger:
    def test_double_admission_and_ghost_moves_are_refused(self):
        ledger = aging_fleet()
        with pytest.raises(Invalid):
            ledger.admit("seg-new", sealed_at=1)
        with pytest.raises(Missing):
            ledger.touched("ghost")
        with pytest.raises(Missing):
            ledger.tier_of("ghost")

    def test_retirement_stops_the_billing(self):
        ledger = aging_fleet()
        before = ledger.monthly_bill()
        ledger.retire("seg-new")
        assert ledger.monthly_bill() < before

    def test_the_bill_prices_each_seat(self):
        ledger = aging_fleet()
        assert ledger.monthly_bill() == 30
        ledger.settle(now=100)
        ledger.settle(now=100)
        assert ledger.monthly_bill() == 10 + 4 + 1

    def test_moves_are_journaled_with_their_evidence(self):
        ledger = aging_fleet()
        ledger.settle(now=100)
        assert any(
            "seg-old: hot -> warm (age 100, heat 0)" in line
            for line in ledger.moves
        )


class TestTheCostReport:
    def test_the_report_names_the_slowest_seat(self):
        ledger = aging_fleet()
        ledger.settle(now=100)
        ledger.settle(now=100)
        report = ledger.query_cost_report(
            ["seg-new", "seg-mid", "seg-old"]
        )
        assert report == (
            "touched 1 cold, 1 hot, 1 warm; slowest seat multiplies "
            "latency by 10"
        )

    def test_an_untouched_query_says_so(self):
        assert aging_fleet().query_cost_report([]) == (
            "the query touched nothing"
        )
