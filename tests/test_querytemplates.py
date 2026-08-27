from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.querytemplates import Hole, QueryTemplate, TemplateBook


def alert_template() -> QueryTemplate:
    return QueryTemplate(
        name="error-watch",
        shape='level:{level} +{word} "{exact}"',
        holes=(
            Hole("level", "keyword"),
            Hole("word", "term"),
            Hole("exact", "term"),
        ),
    )


class TestHoles:
    def test_unknown_hole_types_list_the_choices(self):
        with pytest.raises(Invalid, match="term, keyword, number"):
            Hole("count", "float")

    def test_number_holes_refuse_strings(self):
        with pytest.raises(Invalid, match="not one"):
            Hole("count", "number").fill("7")

    def test_number_holes_pass_integers(self):
        assert Hole("count", "number").fill(7) == "7"

    def test_keyword_holes_refuse_query_syntax(self):
        with pytest.raises(Invalid, match="never operators"):
            Hole("level", "keyword").fill('error" OR "debug')

    def test_term_holes_strip_quotes_silently(self):
        assert Hole("word", "term").fill('time"out') == "timeout"

    def test_empty_values_fill_nothing(self):
        with pytest.raises(Invalid, match="fills nothing"):
            Hole("word", "term").fill("  ")


class TestRendering:
    def test_a_full_render_produces_a_query(self):
        rendered = alert_template().render(
            level="error", word="timeout", exact="connection reset"
        )
        assert rendered == 'level:error +timeout "connection reset"'

    def test_missing_values_are_named(self):
        with pytest.raises(Missing, match="exact, word"):
            alert_template().render(level="error")

    def test_surplus_values_are_a_caller_typo(self):
        with pytest.raises(Invalid, match="calling side"):
            alert_template().render(
                level="error",
                word="timeout",
                exact="reset",
                extra="oops",
            )

    def test_a_hole_with_no_home_is_refused(self):
        with pytest.raises(Invalid, match="no home"):
            QueryTemplate(
                name="orphan",
                shape="just words",
                holes=(Hole("ghost", "term"),),
            )


class TestTheBook:
    def test_saving_twice_bumps_the_version(self):
        book = TemplateBook()
        book.save(alert_template(), who="ops")
        book.save(alert_template(), who="ops")
        _, version = book.render(
            "error-watch",
            level="error",
            word="timeout",
            exact="reset",
        )
        assert version == 2
        assert book.journal == [
            "error-watch v1 saved by ops",
            "error-watch v2 saved by ops",
        ]

    def test_rendering_the_unsaved_is_refused(self):
        with pytest.raises(Missing, match="no template named"):
            TemplateBook().render("phantom")
