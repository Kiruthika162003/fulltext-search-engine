from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.seasonality import SeasonLedger


def umbrella_ledger() -> SeasonLedger:
    ledger = SeasonLedger()
    ledger.observe("umbrella", 2023, 6, 900)
    ledger.observe("umbrella", 2024, 6, 1100)
    ledger.observe("umbrella", 2025, 6, 1000)
    ledger.observe("umbrella", 2023, 1, 50)
    return ledger


class TestObservation:
    def test_periods_stay_on_the_calendar(self):
        with pytest.raises(Invalid, match="off the calendar"):
            SeasonLedger().observe("x", 2026, 13, 1)

    def test_periods_close_once(self):
        ledger = umbrella_ledger()
        with pytest.raises(Invalid, match="close once"):
            ledger.observe("umbrella", 2024, 6, 5)

    def test_history_reads_in_year_order(self):
        assert umbrella_ledger().history("umbrella", 6) == [
            900,
            1100,
            1000,
        ]


class TestJudgment:
    def test_the_annual_monsoon_is_not_a_spike(self):
        verdict = umbrella_ledger().judge("umbrella", 2026, 6, 1200)
        assert "seasonal" in verdict
        assert "what this season does" in verdict
        assert "3 years of memory" in verdict

    def test_a_real_spike_beats_the_seasonal_norm(self):
        verdict = umbrella_ledger().judge("umbrella", 2026, 6, 5000)
        assert verdict.startswith("umbrella: SPIKE")
        assert "5.0x" in verdict

    def test_one_prior_year_is_an_anecdote(self):
        verdict = umbrella_ledger().judge("umbrella", 2026, 1, 40)
        assert "anecdote, not climatology" in verdict

    def test_no_memory_falls_back_to_plain_trending(self):
        verdict = umbrella_ledger().judge("scarf", 2026, 12, 300)
        assert "no seasonal memory" in verdict
        assert "first appearances are" in verdict

    def test_a_silent_history_makes_any_count_news(self):
        ledger = SeasonLedger()
        ledger.observe("gadget", 2025, 3, 0)
        verdict = ledger.judge("gadget", 2026, 3, 10)
        assert "genuinely new" in verdict


class TestMemory:
    def test_the_depth_is_stated(self):
        page = umbrella_ledger().memory_depth("umbrella")
        assert page == "umbrella: memory spans 3 year(s), 2023 to 2025"

    def test_no_memory_says_so(self):
        assert (
            SeasonLedger().memory_depth("ghost")
            == "ghost: no memory at all"
        )
