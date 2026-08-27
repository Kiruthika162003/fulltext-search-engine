from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.phrasesuggest import BigramBook, Continuation


def stocked_book() -> BigramBook:
    book = BigramBook()
    book.learn("the department store opens early")
    book.learn("a department store with seven floors")
    book.learn("the department budget shrank")
    book.learn("the department budget grew")
    book.learn("a department picnic")
    return book


class TestLearning:
    def test_learning_counts_adjacent_pairs(self):
        book = BigramBook()
        added = book.learn("black cat black cat")
        assert added == 3
        assert book.pairs["black"]["cat"] == 2
        assert book.pairs["cat"]["black"] == 1

    def test_stopwords_never_form_pairs(self):
        book = BigramBook()
        book.learn("the cat and the dog")
        assert "the" not in book.pairs
        assert book.pairs["cat"]["dog"] == 1


class TestContinuations:
    def test_the_frequent_follower_ranks_first(self):
        rows = stocked_book().continuations("the department")
        assert rows[0].word == "budget"
        assert rows[0].count == 2
        assert rows[1].word == "store"

    def test_the_floor_hides_single_sightings(self):
        rows = stocked_book().continuations("the department")
        words = [held.word for held in rows]
        assert "picnic" not in words

    def test_only_the_last_word_matters(self):
        rows = stocked_book().continuations("seven floors department")
        assert [held.word for held in rows] == ["budget", "store"]

    def test_an_unknown_tail_continues_nowhere(self):
        assert stocked_book().continuations("the zeppelin") == []

    def test_zero_rows_are_refused(self):
        with pytest.raises(Invalid, match="should not open"):
            stocked_book().continuations("department", limit=0)

    def test_an_all_stopword_phrase_is_refused(self):
        with pytest.raises(Invalid, match="no last"):
            stocked_book().continuations("the of and")


class TestPhrasesAndCoverage:
    def test_suggestions_are_whole_phrases(self):
        assert stocked_book().suggest_phrases("the department") == [
            "department budget",
            "department store",
        ]

    def test_the_line_shows_the_count(self):
        held = Continuation(word="store", count=2)
        assert held.line() == "store (seen 2x)"

    def test_coverage_states_its_floor(self):
        report = stocked_book().coverage()
        assert report.startswith("5 documents read")
        assert "at or above the floor of 2" in report
