from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.safemarkup import Emphasis, audit, escape, render_snippet


class TestEscaping:
    def test_the_dangerous_four_are_neutralized(self):
        assert escape('<script>"a" & b</script>') == (
            "&lt;script&gt;&quot;a&quot; &amp; b&lt;/script&gt;"
        )

    def test_plain_text_passes_untouched(self):
        assert escape("copper kettle") == "copper kettle"


class TestRendering:
    def test_emphasis_lands_where_the_offsets_say(self):
        rendered = render_snippet(
            "the copper kettle", [Emphasis(4, 10)]
        )
        assert rendered == "the <em>copper</em> kettle"

    def test_hostile_documents_render_inert(self):
        rendered = render_snippet(
            "<script>alert(1)</script> kettle",
            [Emphasis(26, 32)],
        )
        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered
        assert "<em>kettle</em>" in rendered

    def test_emphasis_inside_hostile_text_stays_inert(self):
        rendered = render_snippet(
            "<em>fake</em> kettle", [Emphasis(14, 20)]
        )
        assert rendered.count("<em>") == 1
        assert "&lt;em&gt;fake&lt;/em&gt;" in rendered

    def test_overlapping_spans_are_wrong_offsets(self):
        with pytest.raises(Invalid, match="overlap"):
            render_snippet(
                "abcdef", [Emphasis(0, 4), Emphasis(2, 6)]
            )

    def test_spans_past_the_text_are_refused(self):
        with pytest.raises(Invalid, match="holds 3"):
            render_snippet("abc", [Emphasis(1, 9)])

    def test_backward_spans_are_refused(self):
        with pytest.raises(Invalid, match="forward span"):
            Emphasis(5, 5)


class TestTheAudit:
    def test_clean_fragments_pass_with_the_count(self):
        rendered = render_snippet(
            "the copper kettle", [Emphasis(4, 10)]
        )
        assert audit(rendered) == (
            "clean: 1 emphasis span(s), nothing else"
        )

    def test_stray_tags_are_a_leak(self):
        with pytest.raises(Invalid, match="leaking through"):
            audit("<b>bold</b> and <em>fine</em>")

    def test_unclosed_emphasis_is_caught(self):
        with pytest.raises(Invalid, match="does not close"):
            audit("<em>open forever")
