from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.query import Clause, parse


class TestBareTerms:
    def test_words_become_ranked_clauses_on_the_default_field(self):
        query = parse("black cat")
        assert query.groups == (
            (
                Clause(kind="term", field="body", text="black"),
                Clause(kind="term", field="body", text="cat"),
            ),
        )

    def test_field_clauses_aim_at_one_field(self):
        clause = parse("author:meera").groups[0][0]
        assert clause.field == "author"
        assert clause.text == "meera"

    def test_a_half_colon_is_refused(self):
        with pytest.raises(Invalid, match="both sides"):
            parse("author:")


class TestModifiers:
    def test_plus_means_must(self):
        clause = parse("+cat dog").groups[0][0]
        assert clause.required
        assert not clause.prohibited

    def test_minus_means_must_not(self):
        clause = parse("cat -dog").groups[0][1]
        assert clause.prohibited

    def test_a_lone_modifier_is_refused(self):
        with pytest.raises(Invalid, match="modifies nothing"):
            parse("cat +")

    def test_pure_exclusion_needs_an_anchor(self):
        with pytest.raises(Invalid, match="anchor"):
            parse("-cat -dog")


class TestPhrases:
    def test_quoted_words_are_one_phrase_clause(self):
        clause = parse('"black cat"').groups[0][0]
        assert clause.kind == "phrase"
        assert clause.text == "black cat"

    def test_a_fielded_phrase_carries_its_field(self):
        clause = parse('title:"deep work"').groups[0][0]
        assert clause.field == "title"
        assert clause.text == "deep work"

    def test_an_unclosed_quote_carries_its_position(self):
        with pytest.raises(Invalid, match="position 4"):
            parse('cat "black')

    def test_an_empty_phrase_is_refused(self):
        with pytest.raises(Invalid, match="matches nothing"):
            parse('""')


class TestOr:
    def test_or_widens_into_groups(self):
        query = parse("cat OR dog bird")
        assert len(query.groups) == 2
        assert [c.text for c in query.groups[0]] == ["cat"]
        assert [c.text for c in query.groups[1]] == ["dog", "bird"]

    def test_or_needs_both_sides(self):
        with pytest.raises(Invalid, match="both sides"):
            parse("OR cat")
        with pytest.raises(Invalid, match="both sides"):
            parse("cat OR")


class TestCanonical:
    def test_the_tree_prints_back_canonically(self):
        query = parse('+cat -author:raj "black dog" OR bird')
        assert query.canonical() == (
            '+body:cat -author:raj body:"black dog" OR body:bird'
        )

    def test_two_spellings_one_meaning(self):
        assert parse("cat  dog").canonical() == parse("cat dog").canonical()

    def test_empty_queries_are_refused(self):
        with pytest.raises(Invalid, match="refused"):
            parse("   ")
