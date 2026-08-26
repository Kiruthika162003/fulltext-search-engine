"""Minimum should match: between AND's cliff and OR's flood.

A five-word query under AND dies if one word is missing; under OR
it drowns in documents matching one word badly. Minimum should
match is the dial between them: require that at least N of the
optional terms appear, or a percentage rounded toward strictness,
and the query keeps AND's precision spirit with OR's forgiveness.
The rounding rule is stated because it is where implementations
disagree and users notice: 60 percent of five terms is three, 60
percent of four terms is 2.4 and rounds up to three, always up,
because the dial exists to hold a floor and a floor that rounds
down is a floor with a trapdoor. Requirements above the term count
are refused rather than clamped, since asking for six of five is a
bug upstream, not an enthusiasm to accommodate.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment


def floor_from_percent(term_count: int, percent: int) -> int:
    if not 1 <= percent <= 100:
        raise Invalid("the percentage lives between 1 and 100")
    if term_count <= 0:
        raise Invalid("a floor over no terms holds nothing")
    exact = term_count * percent / 100
    floor = int(exact)
    if exact > floor:
        floor += 1
    return floor


@dataclass(frozen=True)
class MinShouldMatch:
    terms: tuple[str, ...]
    floor: int

    def __post_init__(self) -> None:
        if not self.terms:
            raise Invalid("no terms, no floor, no query")
        if self.floor < 1:
            raise Invalid(
                "a floor under one is OR wearing a costume; say OR"
            )
        if self.floor > len(self.terms):
            raise Invalid(
                f"a floor of {self.floor} over {len(self.terms)} "
                f"term(s) is a bug upstream, not an enthusiasm"
            )


def matching_docs(
    segment: Segment, field_name: str, spec: MinShouldMatch
) -> list[tuple[int, int]]:
    """Documents meeting the floor, with how many terms each held."""
    held_count: dict[int, int] = {}
    for term in spec.terms:
        postings = segment.postings_for(field_name, term)
        if postings is None:
            continue
        for doc in postings.docs():
            held_count[doc] = held_count.get(doc, 0) + 1
    return sorted(
        (doc, count)
        for doc, count in held_count.items()
        if count >= spec.floor and segment.is_live(doc)
    )


def dial_report(
    segment: Segment, field_name: str, terms: tuple[str, ...]
) -> str:
    """Every floor from OR to AND, with the match count at each stop."""
    lines = [f"{len(terms)} terms, the dial from OR to AND:"]
    for floor in range(1, len(terms) + 1):
        spec = MinShouldMatch(terms=terms, floor=floor)
        count = len(matching_docs(segment, field_name, spec))
        label = (
            "OR"
            if floor == 1
            else "AND"
            if floor == len(terms)
            else f"at least {floor}"
        )
        lines.append(f"  {label}: {count} document(s)")
    return "\n".join(lines)
