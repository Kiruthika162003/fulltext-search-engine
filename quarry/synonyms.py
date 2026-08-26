"""Synonyms: the query grows wider, and the growth is priced.

A synonym ring says these words mean the same thing here: sofa,
couch, settee. Expansion happens at query time, never at index
time, because index-time expansion bakes today's opinions into
every posting list and unbaking them means reindexing the world.
Expanded terms score with a discount, since the user's own word is
evidence and the ring's word is inference, and an inference that
outranks evidence produces the support ticket where searching for
couch returns sofas above couches. Rings are validated at build
time: a word in two rings is refused because transitive merging
silently glues unrelated meanings, which is how "cool" ends up
meaning both cold and excellent in the same index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

DISCOUNT = 0.6


@dataclass
class SynonymRings:
    analyzer: Analyzer = field(default_factory=Analyzer)
    ring_of: dict[str, int] = field(default_factory=dict)
    members: dict[int, tuple[str, ...]] = field(default_factory=dict)
    next_ring: int = 0

    def declare(self, *words: str) -> int:
        if len(words) < 2:
            raise Invalid("a ring of one is a word talking to itself")
        stemmed = []
        for word in words:
            terms = self.analyzer.terms(word)
            if len(terms) != 1:
                raise Invalid(
                    f"{word!r} does not analyze to one term; rings hold "
                    f"single terms"
                )
            stemmed.append(terms[0])
        if len(set(stemmed)) != len(stemmed):
            raise Invalid(
                f"two of {words} collapse to the same term after "
                f"analysis; the ring already contains itself"
            )
        for term in stemmed:
            if term in self.ring_of:
                raise Invalid(
                    f"{term!r} already belongs to a ring; transitive "
                    f"merging glues unrelated meanings"
                )
        ring = self.next_ring
        self.next_ring += 1
        for term in stemmed:
            self.ring_of[term] = ring
        self.members[ring] = tuple(stemmed)
        return ring

    def expansions(self, term: str) -> tuple[str, ...]:
        ring = self.ring_of.get(term)
        if ring is None:
            return ()
        return tuple(
            member for member in self.members[ring] if member != term
        )

    def ring_count(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class WeightedTerm:
    term: str
    weight: float
    source: str


def expand_terms(
    rings: SynonymRings, terms: list[str], discount: float = DISCOUNT
) -> list[WeightedTerm]:
    if not 0.0 < discount <= 1.0:
        raise Invalid("the discount is a fraction of full evidence")
    out: list[WeightedTerm] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            out.append(WeightedTerm(term=term, weight=1.0, source="typed"))
    for term in terms:
        for grown in rings.expansions(term):
            if grown not in seen:
                seen.add(grown)
                out.append(
                    WeightedTerm(
                        term=grown,
                        weight=discount,
                        source=f"ring of {term}",
                    )
                )
    return out


def expansion_report(rows: list[WeightedTerm]) -> str:
    typed = [row.term for row in rows if row.source == "typed"]
    grown = [row for row in rows if row.source != "typed"]
    lines = [f"typed: {', '.join(typed)}"]
    for row in grown:
        lines.append(
            f"  + {row.term} at {row.weight} ({row.source})"
        )
    if not grown:
        lines.append("  no expansions")
    return "\n".join(lines)
