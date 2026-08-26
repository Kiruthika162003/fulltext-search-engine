from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.prefix import expand_prefix, expansion_report, prefix_docs
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.tokenize import Analyzer


def glossary() -> Segment:
    schema = Schema()
    schema.add_text("body", analyzer=Analyzer(stemming=False))
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "network networking netherlands neat"})
    builder.add({"body": "network cables and nets"})
    builder.add({"body": "unrelated words entirely"})
    return builder.seal("glossary")


class TestExpansion:
    def test_the_walk_finds_the_band(self):
        expansion = expand_prefix(glossary(), "body", "net")
        assert expansion.terms == (
            "netherlands",
            "nets",
            "network",
            "networking",
        )
        assert expansion.band_width == 4

    def test_a_prefix_with_no_band_expands_empty(self):
        expansion = expand_prefix(glossary(), "body", "zzz")
        assert expansion.terms == ()

    def test_the_cap_refuses_the_scan_in_disguise(self):
        with pytest.raises(Invalid, match="wearing a wildcard"):
            expand_prefix(glossary(), "body", "n", cap=2)

    def test_the_leading_wildcard_names_the_real_fix(self):
        with pytest.raises(Invalid, match="reversed field"):
            expand_prefix(glossary(), "body", "*ing")

    def test_the_empty_prefix_is_the_whole_language(self):
        with pytest.raises(Invalid, match="whole language"):
            expand_prefix(glossary(), "body", "")


class TestDocs:
    def test_prefix_docs_union_the_band(self):
        assert prefix_docs(glossary(), "body", "net") == [0, 1]

    def test_a_tight_prefix_narrows_the_answer(self):
        assert prefix_docs(glossary(), "body", "netw") == [0, 1]
        assert prefix_docs(glossary(), "body", "neth") == [0]


class TestReport:
    def test_the_report_brags_about_what_it_skipped(self):
        expansion = expand_prefix(glossary(), "body", "neth")
        report = expansion_report(expansion)
        assert report.startswith("neth*: 1 term(s)")
        assert "instead of all of it" in report
