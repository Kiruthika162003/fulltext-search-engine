from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.scoring import K1, TermStats, bm25_term, explain, saturation


def rare() -> TermStats:
    return TermStats(term="xylophone", document_frequency=2, corpus_docs=1000)


def common() -> TermStats:
    return TermStats(term="black", document_frequency=600, corpus_docs=1000)


class TestIdf:
    def test_rarer_terms_matter_more(self):
        assert rare().idf() > common().idf()

    def test_a_term_in_every_document_scores_tiny_not_negative(self):
        everywhere = TermStats(
            term="the", document_frequency=1000, corpus_docs=1000
        )
        assert 0.0 < everywhere.idf() < 0.001

    def test_impossible_frequencies_are_refused(self):
        with pytest.raises(Invalid, match="more documents than exist"):
            TermStats(term="x", document_frequency=5, corpus_docs=3)
        with pytest.raises(Invalid, match="appears nowhere"):
            TermStats(term="x", document_frequency=0, corpus_docs=3)


class TestSaturation:
    def test_the_second_mention_adds_less(self):
        first = saturation(1, length=10, average_length=10.0)
        second = saturation(2, length=10, average_length=10.0)
        third = saturation(3, length=10, average_length=10.0)
        assert second - first < first
        assert third - second < second - first

    def test_the_curve_flattens_toward_its_ceiling(self):
        stuffed = saturation(1000, length=10, average_length=10.0)
        assert stuffed < K1 + 1.0
        assert stuffed > (K1 + 1.0) * 0.98

    def test_long_documents_prove_less_per_mention(self):
        tweet = saturation(1, length=5, average_length=50.0)
        novel = saturation(1, length=500, average_length=50.0)
        assert tweet > novel

    def test_b_zero_switches_length_off(self):
        short = saturation(1, length=5, average_length=50.0, b=0.0)
        long_doc = saturation(1, length=500, average_length=50.0, b=0.0)
        assert short == long_doc

    def test_an_empty_corpus_cannot_average(self):
        with pytest.raises(Invalid):
            saturation(1, length=5, average_length=0.0)

    def test_zero_frequency_scores_zero(self):
        assert saturation(0, length=5, average_length=10.0) == 0.0


class TestExplain:
    def test_the_factors_sum_to_the_score(self):
        total, factors = explain(
            [(rare(), 1), (common(), 2)],
            length=10,
            average_length=12.0,
        )
        assert total == pytest.approx(
            sum(factor.contribution for factor in factors), abs=1e-6
        )
        assert len(factors) == 2

    def test_each_line_is_auditable(self):
        _, factors = explain(
            [(rare(), 1)], length=10, average_length=10.0
        )
        line = factors[0].line()
        assert line.startswith("xylophone: idf ")
        assert " x saturation " in line

    def test_the_direct_form_matches_the_explained_form(self):
        direct = bm25_term(rare(), 2, length=10, average_length=12.0)
        total, _ = explain(
            [(rare(), 2)], length=10, average_length=12.0
        )
        assert total == pytest.approx(direct, abs=1e-6)
