from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.tokenize import Analyzer, Token, ngrams, stem


class TestSplitting:
    def test_words_split_on_anything_not_alnum(self):
        terms = Analyzer(stemming=False).terms("fast-moving, well tested!")
        assert terms == ["fast", "moving", "well", "tested"]

    def test_the_default_pipeline_end_to_end(self):
        terms = Analyzer().terms("The Cats are running quickly")
        assert terms == ["cat", "runn", "quick"]

    def test_numbers_survive(self):
        assert Analyzer().terms("port 8080 open") == ["port", "8080", "open"]

    def test_empty_text_yields_nothing(self):
        assert Analyzer().tokens("") == []


class TestPositions:
    def test_positions_are_assigned_after_dropping(self):
        tokens = Analyzer(stemming=False).tokens("the black cat")
        assert [(t.text, t.position) for t in tokens] == [
            ("black", 0),
            ("cat", 1),
        ]

    def test_offsets_point_back_at_the_source(self):
        text = "The Cats"
        token = Analyzer().tokens(text)[0]
        assert token == Token(text="cat", position=0, start=4, end=8)
        assert text[token.start : token.end] == "Cats"


class TestStemming:
    def test_one_suffix_comes_off(self):
        assert stem("running") == "runn"
        assert stem("cats") == "cat"
        assert stem("stories") == "stor"

    def test_short_stems_are_left_standing(self):
        assert stem("is") == "is"
        assert stem("bed") == "bed"

    def test_the_same_mistake_on_both_sides(self):
        indexed = Analyzer().terms("running fast")
        queried = Analyzer().terms("runs fast")
        assert indexed[0] == "runn"
        assert queried[0] == "run"


class TestIdentity:
    def test_the_identity_freezes_the_choices(self):
        assert Analyzer().identity() == "lower=1|stop=1|stem=1"
        assert Analyzer(stemming=False).identity() == "lower=1|stop=1|stem=0"


class TestNgrams:
    def test_grams_are_padded_and_slid(self):
        assert ngrams("cat", 3) == ["\x02ca", "cat", "at\x03"]

    def test_a_tiny_term_is_one_gram(self):
        assert ngrams("a", 4) == ["\x02a\x03"]

    def test_width_one_is_refused(self):
        with pytest.raises(Invalid):
            ngrams("cat", 1)
