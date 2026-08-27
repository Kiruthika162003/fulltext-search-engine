from __future__ import annotations

import pytest

from quarry.driftwatch import CorpusProfile, DriftWatch
from quarry.errors import Invalid


def january() -> CorpusProfile:
    return CorpusProfile(
        label="january",
        avg_length=100.0,
        vocab_per_thousand=800.0,
        top_term_share=0.04,
    )


class TestProfiles:
    def test_empty_corpora_are_not_baselines(self):
        with pytest.raises(Invalid, match="do not baseline"):
            CorpusProfile(
                label="void",
                avg_length=0.0,
                vocab_per_thousand=10.0,
                top_term_share=0.1,
            )

    def test_shares_live_in_the_unit_interval(self):
        with pytest.raises(Invalid, match=r"\(0, 1\]"):
            CorpusProfile(
                label="odd",
                avg_length=10.0,
                vocab_per_thousand=10.0,
                top_term_share=1.4,
            )


class TestComparison:
    def test_small_movement_is_noise(self):
        watch = DriftWatch(baseline=january())
        findings, verdict = watch.compare(
            CorpusProfile(
                label="february",
                avg_length=110.0,
                vocab_per_thousand=850.0,
                top_term_share=0.045,
            )
        )
        assert verdict == "steady: all metrics inside tolerance"
        assert all(not held.breached for held in findings)

    def test_one_breach_is_a_note(self):
        watch = DriftWatch(baseline=january())
        _, verdict = watch.compare(
            CorpusProfile(
                label="march",
                avg_length=130.0,
                vocab_per_thousand=820.0,
                top_term_share=0.04,
            )
        )
        assert verdict.startswith("note: one metric")

    def test_correlated_breaches_page(self):
        watch = DriftWatch(baseline=january())
        findings, verdict = watch.compare(
            CorpusProfile(
                label="april",
                avg_length=150.0,
                vocab_per_thousand=1200.0,
                top_term_share=0.04,
            )
        )
        assert verdict.startswith("PAGE: 2 metrics")
        lengths = next(
            held
            for held in findings
            if held.metric_name == "avg_length"
        )
        assert lengths.line() == (
            "avg_length: 100.0 -> 150.0 (+50%, DRIFT)"
        )

    def test_self_comparison_sees_nothing_by_construction(self):
        with pytest.raises(Invalid, match="by construction"):
            DriftWatch(baseline=january()).compare(january())


class TestRebaselining:
    def test_rebaselines_are_deliberate(self):
        watch = DriftWatch(baseline=january())
        message = watch.rebaseline(
            CorpusProfile(
                label="post-migration",
                avg_length=150.0,
                vocab_per_thousand=1200.0,
                top_term_share=0.05,
            ),
            reason="catalog rewrite shipped 2026-08",
        )
        assert "january -> post-migration" in message
        assert watch.baseline.label == "post-migration"

    def test_reasonless_rebaselines_follow_the_drift(self):
        with pytest.raises(Invalid, match="follow the"):
            DriftWatch(baseline=january()).rebaseline(
                january(), reason="  "
            )
