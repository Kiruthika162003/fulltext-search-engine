"""Snippet judging: the two-line preview is graded like a result.

The snippet is most users' entire experience of a document, and
it can fail while the ranking is perfect: a preview that shows
none of the query words, one that opens mid-sentence with a
dangling fragment, one that highlights a stopword's neighbor
instead of the match. The judge scores a snippet against its
query on three declared axes: coverage, the share of query
terms visible in the window; anchoring, whether the window
starts at a word boundary and not mid-token; and density,
whether the matched words sit close enough that the preview
reads as an answer rather than three highlights adrift in
filler. Each axis reports its number, the grade is the
weakest axis because a snippet fails at its worst property,
not its average, and a corpus-wide sweep reports the share of
judged snippets below par, the number that decides whether
the highlighter needs work before the ranker does.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

DENSITY_SPAN = 12
PAR = 0.5


@dataclass(frozen=True)
class SnippetGrade:
    coverage: float
    anchored: bool
    density: float

    def weakest(self) -> float:
        anchor_score = 1.0 if self.anchored else 0.0
        return min(self.coverage, anchor_score, self.density)

    def below_par(self) -> bool:
        return self.weakest() < PAR

    def line(self) -> str:
        anchor = "clean" if self.anchored else "MID-TOKEN"
        verdict = "below par" if self.below_par() else "serviceable"
        return (
            f"coverage {self.coverage}, anchor {anchor}, density "
            f"{self.density}: {verdict}"
        )


def judge_snippet(
    snippet: str, source: str, query_terms: list[str]
) -> SnippetGrade:
    if not query_terms:
        raise Invalid("judging against no query terms judges nothing")
    if not snippet.strip():
        raise Invalid("an empty snippet previews nothing")
    if snippet not in source:
        raise Invalid(
            "the snippet does not appear in its source; judging a "
            "paraphrase grades the wrong artifact"
        )
    analyzer = Analyzer()
    snippet_terms = analyzer.terms(snippet)
    wanted = {
        analyzed
        for term in query_terms
        for analyzed in analyzer.terms(term)
    }
    if not wanted:
        raise Invalid(
            "every query term analyzed to nothing; there is "
            "nothing to look for"
        )
    visible = wanted & set(snippet_terms)
    coverage = round(len(visible) / len(wanted), 4)

    start = source.index(snippet)
    anchored = start == 0 or not (
        source[start - 1].isalnum() and snippet[0].isalnum()
    )

    positions = [
        position
        for position, term in enumerate(snippet_terms)
        if term in wanted
    ]
    if len(positions) <= 1:
        density = 1.0 if positions else 0.0
    else:
        spread = positions[-1] - positions[0]
        density = round(min(1.0, DENSITY_SPAN / max(spread, 1)), 4)

    return SnippetGrade(
        coverage=coverage, anchored=anchored, density=density
    )


def sweep(
    judged: list[SnippetGrade],
) -> str:
    if not judged:
        raise Invalid("a sweep over no snippets sweeps nothing")
    failing = sum(1 for grade in judged if grade.below_par())
    share = failing / len(judged)
    verdict = (
        "the highlighter needs work before the ranker does"
        if share > 0.2
        else "snippets are pulling their weight"
    )
    return (
        f"{failing} of {len(judged)} snippets below par "
        f"({share:.0%}); {verdict}"
    )
