"""The stopword tuner: candidates from the corpus, vetoes from the users.

A stopword list copied from a blog post stops the wrong words for
this corpus, and the corpus knows better: a word in nearly every
document carries almost no signal and a fat posting list, so the
tuner nominates by document frequency ratio. But the corpus does
not know the queries, and stopping a word people actually search
for turns their query into silence, so every nomination is
checked against the query log and a term users type survives no
matter how common it is in documents. The output is a report
that shows its arithmetic per word, because a stopword list that
cannot explain itself gets argued with forever, and applying the
list is a separate deliberate step that returns a fresh analyzer
rather than mutating the one in use.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

NOMINATE_RATIO = 0.6


@dataclass(frozen=True)
class Nomination:
    term: str
    document_ratio: float
    vetoed_by_queries: bool

    def verdict(self) -> str:
        if self.vetoed_by_queries:
            return (
                f"{self.term}: in {self.document_ratio:.0%} of "
                f"documents but users search for it; kept"
            )
        return (
            f"{self.term}: in {self.document_ratio:.0%} of "
            f"documents and no one queries it; stop it"
        )


@dataclass
class StopwordTuner:
    analyzer: Analyzer
    document_terms: list[set[str]]
    queried_terms: set[str]

    def nominate(self) -> list[Nomination]:
        if not self.document_terms:
            raise Invalid(
                "tuning stopwords on zero documents nominates nothing "
                "and means the corpus was never loaded"
            )
        counts: dict[str, int] = {}
        for terms in self.document_terms:
            for term in terms:
                counts[term] = counts.get(term, 0) + 1
        total = len(self.document_terms)
        nominations = []
        for term, count in sorted(counts.items()):
            ratio = count / total
            if ratio < NOMINATE_RATIO:
                continue
            nominations.append(
                Nomination(
                    term=term,
                    document_ratio=ratio,
                    vetoed_by_queries=term in self.queried_terms,
                )
            )
        nominations.sort(
            key=lambda held: (-held.document_ratio, held.term)
        )
        return nominations

    def approved(self) -> list[str]:
        return [
            held.term
            for held in self.nominate()
            if not held.vetoed_by_queries
        ]

    def report(self) -> str:
        nominations = self.nominate()
        if not nominations:
            return (
                f"no term reaches {NOMINATE_RATIO:.0%} of documents; "
                f"this corpus needs no new stopwords"
            )
        lines = [
            f"threshold: present in {NOMINATE_RATIO:.0%} of "
            f"{len(self.document_terms)} documents"
        ]
        lines.extend(held.verdict() for held in nominations)
        stopped = len([n for n in nominations if not n.vetoed_by_queries])
        vetoed = len(nominations) - stopped
        lines.append(
            f"outcome: {stopped} stopped, {vetoed} saved by the "
            f"query log"
        )
        return "\n".join(lines)

    def retuned(self) -> TunedAnalyzer:
        return TunedAnalyzer(
            base=self.analyzer, extra=frozenset(self.approved())
        )


@dataclass(frozen=True)
class TunedAnalyzer:
    """The base analyzer plus corpus-earned stopwords, both sides."""

    base: Analyzer
    extra: frozenset[str]

    def terms(self, text: str) -> list[str]:
        return [
            term
            for term in self.base.terms(text)
            if term not in self.extra
        ]

    def identity(self) -> str:
        added = ",".join(sorted(self.extra)) if self.extra else "none"
        return f"{self.base.identity()}|tuned={added}"


def corpus_term_sets(
    analyzer: Analyzer, documents: list[str]
) -> list[set[str]]:
    return [set(analyzer.terms(text)) for text in documents]
