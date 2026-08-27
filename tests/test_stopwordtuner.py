from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.stopwordtuner import (
    NOMINATE_RATIO,
    StopwordTuner,
    corpus_term_sets,
)
from quarry.tokenize import Analyzer


def catalog_tuner(queried: set[str] | None = None) -> StopwordTuner:
    analyzer = Analyzer()
    documents = [
        "acme widget blue steel",
        "acme gadget red steel",
        "acme sprocket green steel",
        "acme flange blue copper",
        "lone entry without common words",
    ]
    return StopwordTuner(
        analyzer=analyzer,
        document_terms=corpus_term_sets(analyzer, documents),
        queried_terms=queried or set(),
    )


class TestNomination:
    def test_the_brand_word_is_nominated(self):
        terms = [held.term for held in catalog_tuner().nominate()]
        assert "acme" in terms
        assert "steel" in terms

    def test_rare_words_are_never_nominated(self):
        terms = [held.term for held in catalog_tuner().nominate()]
        assert "widget" not in terms
        assert "lone" not in terms

    def test_the_ratio_is_arithmetic_not_vibes(self):
        held = next(
            n for n in catalog_tuner().nominate() if n.term == "acme"
        )
        assert held.document_ratio == 0.8
        assert held.document_ratio >= NOMINATE_RATIO

    def test_zero_documents_are_refused(self):
        empty = StopwordTuner(
            analyzer=Analyzer(),
            document_terms=[],
            queried_terms=set(),
        )
        with pytest.raises(Invalid, match="never loaded"):
            empty.nominate()


class TestTheQueryVeto:
    def test_a_searched_term_survives(self):
        tuner = catalog_tuner(queried={"acme"})
        assert "acme" not in tuner.approved()
        assert "steel" in tuner.approved()

    def test_the_verdicts_explain_both_ways(self):
        tuner = catalog_tuner(queried={"acme"})
        verdicts = [held.verdict() for held in tuner.nominate()]
        assert any("users search for it; kept" in v for v in verdicts)
        assert any("no one queries it; stop it" in v for v in verdicts)

    def test_the_report_totals_the_outcome(self):
        report = catalog_tuner(queried={"acme"}).report()
        assert "1 stopped, 1 saved by the query log" in report
        assert report.startswith("threshold: present in 60%")

    def test_a_clean_corpus_says_so(self):
        analyzer = Analyzer()
        documents = ["apple pear", "cherry plum", "quince medlar"]
        tuner = StopwordTuner(
            analyzer=analyzer,
            document_terms=corpus_term_sets(analyzer, documents),
            queried_terms=set(),
        )
        assert "needs no new stopwords" in tuner.report()


class TestTheTunedAnalyzer:
    def test_the_extra_words_stop_on_both_sides(self):
        tuned = catalog_tuner().retuned()
        assert tuned.terms("acme steel widget") == ["widget"]

    def test_the_identity_names_its_additions(self):
        tuned = catalog_tuner().retuned()
        assert tuned.identity().endswith("|tuned=acme,steel")

    def test_no_approvals_means_a_transparent_wrapper(self):
        analyzer = Analyzer()
        documents = ["apple pear", "cherry plum", "quince medlar"]
        tuner = StopwordTuner(
            analyzer=analyzer,
            document_terms=corpus_term_sets(analyzer, documents),
            queried_terms=set(),
        )
        tuned = tuner.retuned()
        assert tuned.terms("apple cherry") == ["apple", "cherry"]
        assert tuned.identity().endswith("|tuned=none")
