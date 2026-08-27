from __future__ import annotations

import pytest

from quarry.abbrevexpand import AbbrevBook
from quarry.errors import Invalid, Missing


def office_book() -> AbbrevBook:
    book = AbbrevBook()
    book.declare("nda", "non disclosure agreement")
    book.declare("qps", "queries per second")
    return book


class TestDeclaration:
    def test_initials_must_match_in_order(self):
        with pytest.raises(Invalid, match="delusions"):
            AbbrevBook().declare("db", "structured query language")

    def test_case_and_padding_normalize(self):
        book = AbbrevBook()
        assert book.declare(" API ", "Application Programming Interface") == (
            "api -> application programming interface"
        )

    def test_redeclaring_the_same_expansion_is_calm(self):
        book = office_book()
        assert book.declare("nda", "non disclosure agreement") == (
            "nda -> non disclosure agreement"
        )


class TestContests:
    def test_a_second_claim_contests_the_abbreviation(self):
        book = AbbrevBook()
        book.declare("pm", "product manager")
        message = book.declare("pm", "post meridiem")
        assert "CONTESTED" in message
        assert book.expand_term("pm") == ["pm"]

    def test_the_worklist_names_the_dispute(self):
        book = AbbrevBook()
        book.declare("pm", "product manager")
        book.declare("pm", "post meridiem")
        page = book.worklist()
        assert "'product manager' vs 'post meridiem'" in page

    def test_resolution_restores_expansion(self):
        book = AbbrevBook()
        book.declare("pm", "product manager")
        book.declare("pm", "post meridiem")
        book.resolve("pm", "product manager")
        assert book.expand_term("pm") == [
            "pm",
            "product",
            "manager",
        ]
        assert "decisive" in book.worklist()

    def test_resolving_the_undisputed_is_refused(self):
        with pytest.raises(Missing, match="not contested"):
            office_book().resolve("nda", "non disclosure agreement")

    def test_resolution_must_pick_a_real_claim(self):
        book = AbbrevBook()
        book.declare("pm", "product manager")
        book.declare("pm", "post meridiem")
        with pytest.raises(Invalid, match="never a claim"):
            book.resolve("pm", "prime minister")


class TestBothDirections:
    def test_terms_expand_with_their_words(self):
        assert office_book().expand_term("qps") == [
            "qps",
            "queries",
            "per",
            "second",
        ]

    def test_unknown_terms_stay_themselves(self):
        assert office_book().expand_term("kettle") == ["kettle"]

    def test_phrases_abbreviate_back(self):
        book = office_book()
        assert book.abbreviate_phrase("queries per second") == "qps"
        assert book.abbreviate_phrase("warm kettles") is None
