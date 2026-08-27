from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.samplerank import (
    QueryVerdict,
    SampledReview,
    in_sample,
)


class TestSampling:
    def test_membership_is_deterministic(self):
        assert in_sample("body:cat", 0.5) == in_sample("body:cat", 0.5)

    def test_the_share_is_roughly_honored(self):
        joined = sum(
            1
            for n in range(1000)
            if in_sample(f"body:q{n}", 0.2)
        )
        assert 140 <= joined <= 260

    def test_full_shares_take_everyone(self):
        assert in_sample("anything", 1.0)

    def test_empty_shares_are_refused(self):
        with pytest.raises(Invalid, match="samples nothing"):
            in_sample("body:cat", 0.0)


class TestVerdicts:
    def test_grades_follow_the_top_window(self):
        assert QueryVerdict("q", 3).grade() == "good"
        assert QueryVerdict("q", 1).grade() == "mixed"
        assert QueryVerdict("q", 0).grade() == "bad"

    def test_impossible_arithmetic_is_refused(self):
        with pytest.raises(Invalid, match="cannot happen"):
            QueryVerdict("q", 4)


def filled_review() -> SampledReview:
    review = SampledReview(share=1.0)
    for n in range(20):
        review.offer(f"q{n}", 3)
    for n in range(20, 28):
        review.offer(f"q{n}", 1)
    for n in range(28, 32):
        review.offer(f"q{n}", 0)
    return review


class TestReporting:
    def test_thin_samples_refuse_a_verdict(self):
        review = SampledReview(share=1.0)
        review.offer("q", 3)
        assert "margin swallows the signal" in review.report()

    def test_the_report_confesses_it_is_a_sample(self):
        page = filled_review().report()
        assert page.startswith("sampled 32 queries")
        assert "20 good, 8 mixed, 4 bad" in page
        assert "+/- 0.177" in page
        assert page.endswith("This is a sample, not a census")

    def test_the_worst_lead_the_triage_list(self):
        worst = filled_review().worst(top_n=2)
        assert worst[0] == "q28: 0 of 3 relevant"
        assert worst[1] == "q29: 0 of 3 relevant"
