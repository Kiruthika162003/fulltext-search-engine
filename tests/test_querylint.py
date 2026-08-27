from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.query import parse
from quarry.querylint import Finding, gate, lint, lint_report
from quarry.schema import Schema


def library_schema() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.add_text("title")
    schema.seal()
    return schema


class TestFindings:
    def test_a_reasonable_query_is_clean(self):
        findings = lint(parse("body:cat title:mystery"), library_schema())
        assert findings == []

    def test_undeclared_fields_are_named_with_the_roster(self):
        findings = lint(parse("author:doyle"), library_schema())
        assert any(
            "not declared" in held.message
            and "body, title" in held.message
            for held in findings
        )

    def test_single_letters_draw_a_warning(self):
        findings = lint(parse("body:cat body:x"), library_schema())
        assert any(
            held.severity == "warn" and "'x'" in held.message
            for held in findings
        )

    def test_long_phrases_smell_of_pasting(self):
        pasted = '"one two three four five six seven eight nine ten"'
        findings = lint(parse(pasted), library_schema())
        assert any(
            "pasted sentence" in held.message for held in findings
        )

    def test_required_and_forbidden_is_silence(self):
        findings = lint(parse("body:cat -body:cat"), library_schema())
        assert any(
            "silence by construction" in held.message
            for held in findings
        )

    def test_refusals_sort_before_warnings(self):
        findings = lint(
            parse("body:x ghost:cat"), library_schema()
        )
        assert findings[0].severity == "refuse"


class TestTheGate:
    def test_warnings_pass_through_the_gate(self):
        findings = gate(parse("body:cat body:x"), library_schema())
        assert len(findings) == 1
        assert findings[0].severity == "warn"

    def test_refusals_raise_with_the_diagnosis(self):
        with pytest.raises(Invalid, match="refused by lint"):
            gate(parse("ghost:cat"), library_schema())

    def test_all_stopword_queries_are_refused(self):
        with pytest.raises(Invalid, match="matches everything badly"):
            gate(parse("body:the body:of"), library_schema())


class TestTheReport:
    def test_clean_queries_say_clean(self):
        assert lint_report([]) == "clean query"

    def test_lines_carry_their_severity(self):
        page = lint_report(
            [Finding(severity="warn", message="too short")]
        )
        assert page == "[warn] too short"
