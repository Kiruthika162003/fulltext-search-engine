from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.hedgedreads import HedgedReader


def reader() -> HedgedReader:
    return HedgedReader(
        replicas=("east", "west"), hedge_delay_ms=50
    )


class TestConstruction:
    def test_one_box_is_a_retry_not_insurance(self):
        with pytest.raises(Invalid, match="retry, not insurance"):
            HedgedReader(replicas=("alone",), hedge_delay_ms=50)

    def test_zero_delay_doubles_every_read(self):
        with pytest.raises(Invalid, match="for nothing"):
            HedgedReader(replicas=("a", "b"), hedge_delay_ms=0)

    def test_the_hedge_goes_elsewhere_by_construction(self):
        assert reader().pick_hedge_target("east") == "west"
        assert reader().pick_hedge_target("west") == "east"


class TestObservation:
    def test_fast_primaries_never_hedge(self):
        held = reader()
        outcome = held.observe("q", "east", primary_latency=30)
        assert not outcome.hedged
        assert outcome.winner == "primary"

    def test_slow_primaries_hedge_and_the_faster_wins(self):
        held = reader()
        outcome = held.observe(
            "q", "east", primary_latency=200, hedge_latency=40
        )
        assert outcome.hedged
        assert outcome.winner == "hedge"
        assert outcome.first_latency == 90

    def test_a_hedge_that_loses_is_counted_as_waste(self):
        held = reader()
        outcome = held.observe(
            "q", "east", primary_latency=60, hedge_latency=100
        )
        assert outcome.hedged
        assert outcome.winner == "primary"

    def test_slow_reads_must_report_the_hedge(self):
        with pytest.raises(Invalid, match="must be"):
            reader().observe("q", "east", primary_latency=200)


class TestTheLedger:
    def test_the_ledger_prices_the_insurance(self):
        held = reader()
        held.observe("a", "east", primary_latency=30)
        held.observe("b", "east", primary_latency=200, hedge_latency=40)
        held.observe("c", "east", primary_latency=60, hedge_latency=100)
        page = held.ledger()
        assert "3 reads, 2 hedged (67%)" in page
        assert "won 1 and wasted 1" in page

    def test_worth_it_needs_wins_on_half_the_hedges(self):
        held = reader()
        held.observe("a", "east", primary_latency=200, hedge_latency=40)
        assert held.worth_it()
        held.observe("b", "east", primary_latency=60, hedge_latency=100)
        assert held.worth_it()
        held.observe("c", "east", primary_latency=60, hedge_latency=100)
        assert not held.worth_it()

    def test_an_unused_hedge_says_so(self):
        held = reader()
        held.observe("a", "east", primary_latency=10)
        assert "never reached" in held.ledger()
