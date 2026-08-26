from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.rerank import ClickBook, flywheel_check, rerank


def biased_history() -> ClickBook:
    """The incumbent sits at position 0; the challenger at position 5."""
    book = ClickBook()
    for _ in range(100):
        book.shown(1, 0)
        book.shown(2, 5)
    for _ in range(30):
        book.clicked(1)
    for _ in range(20):
        book.clicked(2)
    return book


class TestTheBook:
    def test_clicks_on_the_unshown_blame_instrumentation(self):
        with pytest.raises(Invalid, match="lying"):
            ClickBook().clicked(9)

    def test_negative_positions_are_refused(self):
        with pytest.raises(Invalid):
            ClickBook().shown(1, -1)

    def test_examination_discounts_the_deep_positions(self):
        book = biased_history()
        assert book.expected_examinations(1) == 100.0
        assert book.expected_examinations(2) == pytest.approx(35.0)

    def test_the_corrected_rate_is_clicks_per_look(self):
        book = biased_history()
        assert book.corrected_rate(1) == pytest.approx(0.3)
        assert book.corrected_rate(2) == pytest.approx(0.5714, abs=1e-3)

    def test_the_never_shown_have_no_rate(self):
        assert ClickBook().corrected_rate(7) is None


class TestReranking:
    def test_the_corrected_challenger_overtakes(self):
        book = biased_history()
        ranked = [(1, 1.0), (2, 0.95)]
        out = rerank(ranked, book, blend=0.3)
        assert out[0].external == 2

    def test_cold_documents_keep_their_pure_score(self):
        book = biased_history()
        out = rerank([(3, 0.8)], book)
        assert out[0].final == 0.8
        assert out[0].behaviour is None

    def test_behaviour_is_bounded_by_the_blend(self):
        book = ClickBook()
        for _ in range(10):
            book.shown(1, 0)
            book.clicked(1)
            book.clicked(1)
        out = rerank([(1, 1.0)], book, blend=0.3)
        assert out[0].final <= 1.0 * 0.7 + 1.0 * 0.3 * 2.0 + 1e-9

    def test_a_blend_of_one_is_replacement_not_tuning(self):
        with pytest.raises(Invalid, match="does not replace"):
            rerank([(1, 1.0)], ClickBook(), blend=1.0)


class TestTheFlywheel:
    def test_the_check_names_the_flywheel_when_it_spins(self):
        verdict = flywheel_check(biased_history(), 1, 2)
        assert "the flywheel talking" in verdict

    def test_merit_is_also_a_possible_answer(self):
        book = ClickBook()
        for _ in range(100):
            book.shown(1, 0)
            book.shown(2, 5)
        for _ in range(80):
            book.clicked(1)
        for _ in range(5):
            book.clicked(2)
        assert "holds on merit" in flywheel_check(book, 1, 2)

    def test_no_evidence_refuses_to_judge(self):
        assert "not enough evidence" in flywheel_check(ClickBook(), 1, 2)
