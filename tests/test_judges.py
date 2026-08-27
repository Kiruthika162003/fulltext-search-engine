from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.judges import (
    JudgmentPool,
    agreement_verdict,
    cohens_kappa,
)


class TestPooling:
    def test_the_pool_unions_every_system(self):
        pool = JudgmentPool()
        pool.contribute("bm25", [1, 2, 3])
        pool.contribute("boosted", [3, 4])
        assert set(pool.pooled()) == {1, 2, 3, 4}

    def test_the_shuffle_is_deterministic_and_hides_rank(self):
        pool = JudgmentPool()
        pool.contribute("bm25", [1, 2, 3, 4, 5])
        first = pool.pooled()
        second = pool.pooled()
        assert first == second
        assert first != [1, 2, 3, 4, 5]

    def test_empty_contributions_are_refused(self):
        with pytest.raises(Invalid, match="widen the pool"):
            JudgmentPool().contribute("bm25", [])

    def test_the_homework_audit_names_the_dominant_system(self):
        pool = JudgmentPool()
        pool.contribute("bm25", list(range(50)))
        pool.contribute("boosted", [1, 2])
        audit = pool.provenance_audit()
        assert audit.startswith("POOL BIAS")
        assert "grading its own homework" in audit

    def test_a_balanced_pool_reads_plainly(self):
        pool = JudgmentPool()
        pool.contribute("bm25", [1, 2, 3])
        pool.contribute("boosted", [4, 5, 6])
        audit = pool.provenance_audit()
        assert audit.startswith("pool provenance:")


class TestKappa:
    def test_perfect_agreement_is_one(self):
        labels = {doc: doc % 2 == 0 for doc in range(10)}
        assert cohens_kappa(labels, dict(labels)) == 1.0

    def test_agreement_by_accident_scores_low(self):
        left = {doc: True for doc in range(10)}
        right = {doc: True for doc in range(9)}
        right[9] = False
        kappa = cohens_kappa(left, right)
        assert kappa <= 0.0

    def test_genuine_disagreement_lands_between(self):
        left = {doc: doc < 6 for doc in range(10)}
        right = {doc: doc < 4 for doc in range(10)}
        kappa = cohens_kappa(left, right)
        assert 0.0 < kappa < 1.0

    def test_a_thin_overlap_is_refused(self):
        with pytest.raises(Invalid, match="too few"):
            cohens_kappa({1: True}, {1: True})


class TestTheVerdict:
    def test_the_noise_line_names_the_inheritance(self):
        verdict = agreement_verdict(0.3)
        assert "inherits it" in verdict

    def test_the_middle_band_says_adjudicate(self):
        assert "adjudicate" in agreement_verdict(0.55)

    def test_solid_agreement_reads_solid(self):
        assert agreement_verdict(0.8).endswith("solid agreement")
