"""Field boosts: a title hit outweighs a body hit, by a declared number.

Multi-field ranking is a weighted sum with the weights written down:
each field carries a boost, a match in that field multiplies its
BM25 contribution by the boost, and the weights live in one profile
object so the ranking configuration can be diffed, versioned, and
argued about in review instead of scattered across call sites. Two
disciplines keep the sums honest. Boosts are per-field, never
per-document, because a per-document boost is an editorial override
wearing a ranking costume, and those get their own explicit pin
mechanism with an audit trail. And the neutral boost is exactly
1.0, so a profile that boosts nothing ranks identically to plain
BM25, which the tests verify rather than assume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.query import Query
from quarry.scoring import TermStats, bm25_term
from quarry.searcher import match_group
from quarry.writer import Index


@dataclass(frozen=True)
class BoostProfile:
    name: str
    weights: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        seen = set()
        for field_name, weight in self.weights:
            if field_name in seen:
                raise Invalid(
                    f"{self.name}: {field_name} is boosted twice; one "
                    f"field, one number"
                )
            seen.add(field_name)
            if weight <= 0:
                raise Invalid(
                    f"{self.name}: {field_name} boost {weight} would "
                    f"erase or invert matches; boosts are positive"
                )

    def weight_of(self, field_name: str) -> float:
        for held, weight in self.weights:
            if held == field_name:
                return weight
        return 1.0

    def diff(self, other: BoostProfile) -> list[str]:
        lines = []
        fields = {name for name, _ in self.weights} | {
            name for name, _ in other.weights
        }
        for field_name in sorted(fields):
            before = self.weight_of(field_name)
            after = other.weight_of(field_name)
            if before != after:
                lines.append(f"{field_name}: {before} -> {after}")
        return lines


NEUTRAL = BoostProfile(name="neutral", weights=())


@dataclass(frozen=True)
class Pin:
    """The editorial override, explicit and journaled."""

    external: int
    query_text: str
    who: str
    reason: str


@dataclass
class PinBoard:
    pins: list[Pin] = field(default_factory=list)

    def pin(self, external: int, query_text: str, who: str, reason: str) -> None:
        if not reason.strip():
            raise Invalid(
                "a pin without a reason is exactly the quiet override "
                "boosts refuse to be"
            )
        self.pins.append(
            Pin(
                external=external,
                query_text=query_text,
                who=who,
                reason=reason,
            )
        )

    def pinned_for(self, query_text: str) -> list[int]:
        return [
            pin.external
            for pin in self.pins
            if pin.query_text == query_text
        ]

    def journal(self) -> str:
        if not self.pins:
            return "no pins; the ranking speaks for itself"
        return "\n".join(
            f"{pin.query_text!r} -> doc {pin.external} "
            f"({pin.who}: {pin.reason})"
            for pin in self.pins
        )


@dataclass(frozen=True)
class BoostedHit:
    external: int
    score: float
    pinned: bool = False


def boosted_search(
    index: Index,
    query: Query,
    profile: BoostProfile = NEUTRAL,
    pins: PinBoard | None = None,
    query_text: str = "",
    limit: int = 10,
) -> list[BoostedHit]:
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    terms: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in query.groups:
        for clause in group:
            if clause.prohibited:
                continue
            declared = index.schema.get(clause.field)
            if declared.kind != "text":
                continue
            for term in declared.analyzer.terms(clause.text):
                row = (clause.field, term)
                if row not in seen:
                    seen.add(row)
                    terms.append(row)
    total_docs = sum(segment.doc_count() for segment in index.segments)
    frequencies: dict[tuple[str, str], int] = {}
    lengths: dict[str, int] = {}
    for segment in index.segments:
        for field_name, held in segment.lengths.items():
            lengths[field_name] = lengths.get(field_name, 0) + sum(held)
        for row in terms:
            held_list = segment.postings_for(*row)
            if held_list is not None:
                frequencies[row] = (
                    frequencies.get(row, 0) + held_list.document_frequency()
                )
    ranked = []
    for segment in index.segments:
        matched: list[int] = []
        for group in query.groups:
            for doc in match_group(segment, group):
                if doc not in matched:
                    matched.append(doc)
        for doc in matched:
            if not segment.is_live(doc):
                continue
            score = 0.0
            for field_name, term in terms:
                held_list = segment.postings_for(field_name, term)
                if held_list is None:
                    continue
                posting = held_list.find(doc)
                if posting is None:
                    continue
                average = (
                    lengths.get(field_name, 0) / total_docs
                    if total_docs
                    else 0.0
                )
                score += profile.weight_of(field_name) * bm25_term(
                    TermStats(
                        term=term,
                        document_frequency=frequencies[(field_name, term)],
                        corpus_docs=total_docs,
                    ),
                    posting.frequency,
                    length=segment.field_length(field_name, doc),
                    average_length=average,
                )
            ranked.append(
                BoostedHit(
                    external=index.external_id(segment.name, doc),
                    score=round(score, 6),
                )
            )
    ranked.sort(key=lambda hit: (-hit.score, hit.external))
    if pins is not None and query_text:
        front = []
        for external in pins.pinned_for(query_text):
            if not any(hit.external == external for hit in ranked):
                raise Missing(
                    f"pin for doc {external} but the query does not "
                    f"match it; a pin cannot conjure relevance"
                )
            front.append(BoostedHit(external=external, score=0.0, pinned=True))
        rest = [
            hit
            for hit in ranked
            if hit.external not in {p.external for p in front}
        ]
        ranked = front + rest
    return ranked[:limit]
