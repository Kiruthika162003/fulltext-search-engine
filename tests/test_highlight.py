from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.highlight import Span, best_window, mark, matched_spans, snippet
from quarry.tokenize import Analyzer


class TestSpans:
    def test_matches_point_at_the_original_bytes(self):
        spans = matched_spans(
            "The Cats sat", Analyzer(), terms={"cat"}
        )
        assert spans == [Span(start=4, end=8)]

    def test_no_match_no_spans(self):
        assert matched_spans("quiet text", Analyzer(), terms={"cat"}) == []


class TestMarking:
    def test_the_original_casing_survives_the_marks(self):
        spans = matched_spans("The Cats sat", Analyzer(), terms={"cat"})
        assert mark("The Cats sat", spans) == "The [Cats] sat"

    def test_multiple_marks_in_order(self):
        text = "black cat, black dog"
        spans = matched_spans(text, Analyzer(), terms={"black"})
        assert mark(text, spans) == "[black] cat, [black] dog"

    def test_overlapping_spans_are_refused(self):
        with pytest.raises(Invalid, match="overlapping"):
            mark("abcdef", [Span(0, 4), Span(2, 6)])

    def test_no_spans_returns_the_text_untouched(self):
        assert mark("as written", []) == "as written"


class TestWindows:
    def test_the_densest_window_wins(self):
        text = "cat alone here" + " filler" * 20 + " cat cat cat together"
        spans = matched_spans(text, Analyzer(), terms={"cat"})
        start, end = best_window(text, spans, width=30)
        assert text.index("cat cat cat") <= start + 30
        assert end - start >= 20

    def test_windows_never_open_mid_word(self):
        text = "abcdefghij klmnopqrst uvwxyz"
        start, end = best_window(text, [Span(11, 21)], width=10)
        assert start == 11
        assert text[end - 1].isalnum() is False or end == len(text) or (
            not text[end].isalnum()
        )

    def test_zero_width_is_refused(self):
        with pytest.raises(Invalid):
            best_window("text", [], width=0)


class TestSnippets:
    def test_a_snippet_marks_and_trims_with_ellipses(self):
        text = "opening words here " * 5 + "the black cat sat " + "closing" * 5
        made = snippet(text, Analyzer(), terms={"black", "cat"}, width=30)
        assert "[black] [cat]" in made
        assert made.startswith("...")

    def test_no_match_falls_back_to_the_opening(self):
        text = "The first line of a long document " + "x" * 200
        made = snippet(text, Analyzer(), terms={"zebra"}, width=20)
        assert made.startswith("The first line")
        assert made.endswith("...")

    def test_a_short_text_needs_no_ellipses(self):
        made = snippet("black cat", Analyzer(), terms={"cat"}, width=60)
        assert made == "black [cat]"
