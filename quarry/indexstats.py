"""Corpus statistics: the shape of the language, measured on arrival.

A healthy text corpus has a shape: a few terms carry most of the
occurrences, the tail is long and thin, and the vocabulary grows
with the corpus but ever more slowly. The statistics here measure
that shape so its absence can raise an eyebrow: the top-heaviness
ratio says what share of all occurrences the ten busiest terms
carry, the hapax share counts terms seen exactly once, and the
growth curve records vocabulary size at sampling points as the
corpus grows. None of these are alarms on their own; they are the
baseline that makes tomorrow's anomaly visible, because a corpus
whose hapax share suddenly doubles is usually a corpus that just
ingested a file of serial numbers, and the time to notice is
before the vocabulary trie eats the heap.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.segment import Segment

TOP_BUSY = 10


@dataclass(frozen=True)
class CorpusShape:
    total_occurrences: int
    vocabulary_size: int
    top_heaviness: float
    hapax_share: float

    def eyebrow_lines(self) -> list[str]:
        raised = []
        if self.hapax_share > 0.8:
            raised.append(
                f"hapax share {self.hapax_share:.0%}: most terms appear "
                f"once; serial numbers or ids may be flooding the "
                f"vocabulary"
            )
        if self.top_heaviness < 0.05:
            raised.append(
                f"top {TOP_BUSY} terms carry only "
                f"{self.top_heaviness:.0%}: no term repeats much, which "
                f"is not how language behaves"
            )
        return raised


def shape_of(segment: Segment, field_name: str) -> CorpusShape:
    occurrences: dict[str, int] = {}
    for (held_field, term), postings in segment.postings.items():
        if held_field != field_name:
            continue
        occurrences[term] = sum(
            posting.frequency for posting in postings.rows
        )
    if not occurrences:
        raise Invalid(
            f"no terms indexed under {field_name}; a shape of nothing"
        )
    total = sum(occurrences.values())
    busiest = sorted(occurrences.values(), reverse=True)[:TOP_BUSY]
    hapax = sum(1 for count in occurrences.values() if count == 1)
    return CorpusShape(
        total_occurrences=total,
        vocabulary_size=len(occurrences),
        top_heaviness=round(sum(busiest) / total, 4),
        hapax_share=round(hapax / len(occurrences), 4),
    )


@dataclass
class GrowthCurve:
    sample_every: int = 100
    points: list[tuple[int, int]] = field(default_factory=list)
    documents_seen: int = 0
    vocabulary: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.sample_every <= 0:
            raise Invalid("sampling needs a positive stride")

    def observe(self, terms: list[str]) -> None:
        self.documents_seen += 1
        self.vocabulary.update(terms)
        if self.documents_seen % self.sample_every == 0:
            self.points.append(
                (self.documents_seen, len(self.vocabulary))
            )

    def slowing(self) -> bool:
        """New vocabulary per document should fall as the corpus grows."""
        if len(self.points) < 3:
            raise Invalid(
                "the curve needs three points before it has a shape"
            )
        rates = []
        previous_docs, previous_vocab = 0, 0
        for docs, vocab in self.points:
            rates.append(
                (vocab - previous_vocab) / (docs - previous_docs)
            )
            previous_docs, previous_vocab = docs, vocab
        return rates[-1] < rates[0]

    def curve_report(self) -> str:
        rows = ", ".join(
            f"{docs}:{vocab}" for docs, vocab in self.points
        )
        return f"vocabulary growth (docs:terms) {rows}"
