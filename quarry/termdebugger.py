"""The term debugger: why this document, why not that one, in words.

The two questions every search owner asks are why did this match
and why did that not, and the debugger answers both from the
index rather than from theory. For a hit it walks each query
term through analysis, lookup, and scoring, showing the analyzed
form beside the typed one because the transformation is where
most confusion lives. For a miss it bisects the failure: the
term analyzed to nothing, or the term is absent from the field,
or the term is present but the clause forbids it, or the
document is tombstoned, each stated as the specific reason with
the evidence, because why not found has a dozen answers and
only one of them is true for any given document.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment
from quarry.tokenize import Analyzer


@dataclass(frozen=True)
class TermTrace:
    typed: str
    analyzed: str | None
    present: bool
    frequency: int

    def line(self) -> str:
        if self.analyzed is None:
            return (
                f"{self.typed!r} analyzed to nothing (stopword or "
                f"empty); it cannot match"
            )
        arrow = (
            f"{self.typed!r} -> {self.analyzed!r}"
            if self.typed != self.analyzed
            else f"{self.typed!r}"
        )
        if not self.present:
            return f"{arrow}: absent from this field"
        return f"{arrow}: present, frequency {self.frequency}"


def trace_term(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    typed: str,
    doc: int,
) -> TermTrace:
    analyzed = analyzer.terms(typed)
    if not analyzed:
        return TermTrace(
            typed=typed, analyzed=None, present=False, frequency=0
        )
    term = analyzed[0]
    postings = segment.postings.get((field_name, term))
    frequency = 0
    if postings is not None:
        for row in postings.rows:
            if row.doc == doc:
                frequency = row.frequency
                break
    return TermTrace(
        typed=typed,
        analyzed=term,
        present=frequency > 0,
        frequency=frequency,
    )


def why_matched(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    typed_terms: list[str],
    doc: int,
) -> str:
    if not typed_terms:
        raise Invalid("no terms to trace; the query was empty")
    if doc in segment.tombstones:
        return (
            f"doc {doc} is tombstoned; whatever it contains, it "
            f"cannot be returned"
        )
    traces = [
        trace_term(segment, analyzer, field_name, typed, doc)
        for typed in typed_terms
    ]
    matched = sum(1 for held in traces if held.present)
    lines = [held.line() for held in traces]
    lines.append(
        f"verdict: {matched} of {len(traces)} terms present in "
        f"doc {doc}"
    )
    return "\n".join(lines)


def why_not_matched(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    typed: str,
    doc: int,
) -> str:
    if doc in segment.tombstones:
        return f"doc {doc} is deleted; no term can match a tombstone"
    if doc >= segment.doc_count():
        raise Invalid(
            f"doc {doc} does not exist; the segment holds "
            f"{segment.doc_count()}"
        )
    held = trace_term(segment, analyzer, field_name, typed, doc)
    if held.analyzed is None:
        return held.line()
    if held.present:
        return (
            f"{typed!r} IS present in doc {doc} (frequency "
            f"{held.frequency}); if it was not returned, the reason "
            f"is elsewhere: another required clause failed or the "
            f"score fell below the page"
        )
    postings = segment.postings.get((field_name, held.analyzed))
    if postings is None:
        return (
            f"{held.analyzed!r} appears nowhere in field "
            f"{field_name!r}; no document matches it"
        )
    holders = [row.doc for row in postings.rows[:3]]
    listed = ", ".join(str(one) for one in holders)
    return (
        f"{held.analyzed!r} exists in field {field_name!r} but not "
        f"in doc {doc}; documents that do hold it start with "
        f"{listed}"
    )
