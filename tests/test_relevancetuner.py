from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.relevancetuner import (
    B_GRID,
    K1_GRID,
    Judgment,
    TinyCorpus,
    tune,
    tuning_report,
)
from quarry.scoring import K1, B


def corpus() -> TinyCorpus:
    return TinyCorpus(
        frequencies=(
            {"cat": 3, "nap": 1},
            {"cat": 1, "dog": 1, "walk": 6},
            {"dog": 2, "walk": 2},
            {"cat": 1, "essay": 30, "walk": 4},
        )
    )


JUDGMENTS = (
    Judgment(terms=("cat",), relevant=frozenset({0})),
    Judgment(terms=("dog", "walk"), relevant=frozenset({2})),
)


class TestTheCorpus:
    def test_lengths_and_averages_are_arithmetic(self):
        held = corpus()
        assert held.length(0) == 4
        assert held.length(3) == 35
        assert held.average_length() == 12.75

    def test_ranking_prefers_the_dense_document(self):
        ranked = corpus().rank(["cat"], k1=K1, b=B)
        assert ranked[0] == 0

    def test_unmatched_documents_never_rank(self):
        ranked = corpus().rank(["dog"], k1=K1, b=B)
        assert 0 not in ranked
        assert 3 not in ranked

    def test_an_empty_corpus_is_refused(self):
        with pytest.raises(Invalid, match="cannot be tuned"):
            TinyCorpus(frequencies=())


class TestTuning:
    def test_the_grid_is_fully_scored(self):
        _, cells = tune(corpus(), JUDGMENTS)
        assert len(cells) == len(K1_GRID) * len(B_GRID)

    def test_the_winner_finds_both_answers_first(self):
        best, _ = tune(corpus(), JUDGMENTS)
        assert best.mrr == 1.0

    def test_ties_do_not_churn_the_folklore(self):
        best, cells = tune(corpus(), JUDGMENTS)
        top = max(cell.mrr for cell in cells)
        folklore = next(
            cell for cell in cells if cell.k1 == K1 and cell.b == B
        )
        if folklore.mrr == top:
            assert (best.k1, best.b) == (K1, B)

    def test_no_judgments_are_refused(self):
        with pytest.raises(Invalid, match="toward nothing"):
            tune(corpus(), ())


class TestTheReport:
    def test_every_cell_prints(self):
        best, cells = tune(corpus(), JUDGMENTS)
        page = tuning_report(best, cells)
        assert len(page.splitlines()) == len(cells) + 1

    def test_the_shape_is_named(self):
        best, cells = tune(corpus(), JUDGMENTS)
        page = tuning_report(best, cells)
        assert (
            "plateau to stand on" in page
            or "spike to distrust" in page
        )

    def test_the_winner_line_carries_the_tie_count(self):
        best, cells = tune(corpus(), JUDGMENTS)
        page = tuning_report(best, cells).splitlines()[-1]
        assert page.startswith("winner: ")
        assert "cell(s) tie" in page
