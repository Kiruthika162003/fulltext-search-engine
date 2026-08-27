"""A linter for queries: bad searches diagnosed before they run.

Most terrible search experiences are terrible queries, and the
engine can say so before spending a traversal: a query that is
all stopwords will match everything badly, a lone wildcard-ish
fragment of one letter matches nothing anyone meant, a phrase
longer than eight words is a pasted sentence hunting for an
exact copy, mixing a term with its own negation guarantees
silence, and a field the schema never declared will be refused
downstream anyway so the lint says it early with the declared
list. Each finding carries a severity, refuse or warn, and the
lint never edits the query, because a linter that rewrites
behind the user's back becomes the bug it was hired to catch.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.schema import Schema
from quarry.tokenize import STOPWORDS

PHRASE_LIMIT = 8


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str

    def line(self) -> str:
        return f"[{self.severity}] {self.message}"


def _clauses(query: Query):
    for group in query.groups:
        yield from group


def lint(query: Query, schema: Schema) -> list[Finding]:
    findings: list[Finding] = []
    declared = set(schema.fields)
    seen_terms: set[tuple[str, str]] = set()
    negated: set[tuple[str, str]] = set()
    informative = 0

    for clause in _clauses(query):
        if clause.field not in declared:
            listed = ", ".join(sorted(declared))
            findings.append(
                Finding(
                    severity="refuse",
                    message=(
                        f"field {clause.field!r} is not declared; "
                        f"the schema has {listed}"
                    ),
                )
            )
        if clause.kind == "phrase":
            words = clause.text.split()
            if len(words) > PHRASE_LIMIT:
                findings.append(
                    Finding(
                        severity="warn",
                        message=(
                            f"a {len(words)}-word phrase is a pasted "
                            f"sentence hunting for an exact copy; "
                            f"drop the quotes"
                        ),
                    )
                )
        else:
            if len(clause.text) == 1:
                findings.append(
                    Finding(
                        severity="warn",
                        message=(
                            f"the single letter {clause.text!r} "
                            f"matches nothing anyone meant"
                        ),
                    )
                )
            key = (clause.field, clause.text)
            if clause.prohibited:
                negated.add(key)
            else:
                seen_terms.add(key)
        if not clause.prohibited and clause.text not in STOPWORDS:
            informative += 1

    for field_name, text in sorted(seen_terms & negated):
        findings.append(
            Finding(
                severity="refuse",
                message=(
                    f"{field_name}:{text} is both required and "
                    f"forbidden; that query is silence by "
                    f"construction"
                ),
            )
        )
    if informative == 0:
        findings.append(
            Finding(
                severity="refuse",
                message=(
                    "every positive term is a stopword; this "
                    "matches everything badly"
                ),
            )
        )
    findings.sort(key=lambda held: (held.severity != "refuse", held.message))
    return findings


def gate(query: Query, schema: Schema) -> list[Finding]:
    """Warnings pass, refusals raise; the caller sees both."""
    findings = lint(query, schema)
    refusals = [
        held for held in findings if held.severity == "refuse"
    ]
    if refusals:
        summary = "; ".join(held.message for held in refusals)
        raise Invalid(f"query refused by lint: {summary}")
    return findings


def lint_report(findings: list[Finding]) -> str:
    if not findings:
        return "clean query"
    return "\n".join(held.line() for held in findings)
