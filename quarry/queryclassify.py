"""Query intent classification: navigation, lookup, and exploration.

A search box receives three different jobs wearing one input
field: navigational queries want the one page the user already
knows exists, lookups want a fact from anywhere credible, and
exploration wants a shelf to browse. The classifier reads
structural signals rather than guessing at minds: quoted
phrases and field prefixes signal precision, question words
signal lookup, short unique-term queries whose terms
concentrate in few documents lean navigational, and long or
generic queries lean exploratory. Each verdict returns its
signals with their individual leanings, because a
classification that cannot show its work gets overridden by
the first anecdote, and the downstream policy per class is
declared here as data: navigational tightens to AND and boosts
title, exploratory loosens toward OR with diversity, lookup
sits between.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

QUESTION_WORDS = frozenset(
    "who what when where why how which whose".split()
)

POLICY = {
    "navigational": "AND semantics, title boosted, top 3 shown",
    "lookup": "standard ranking, snippet-first presentation",
    "exploratory": "OR leaning, diversity on, facets shown",
}


@dataclass(frozen=True)
class Signal:
    name: str
    leaning: str

    def line(self) -> str:
        return f"{self.name} -> {self.leaning}"


@dataclass(frozen=True)
class Intent:
    label: str
    signals: tuple[Signal, ...]

    def policy(self) -> str:
        return POLICY[self.label]

    def explain(self) -> str:
        lines = [signal.line() for signal in self.signals]
        lines.append(f"verdict: {self.label} ({self.policy()})")
        return "\n".join(lines)


def classify(
    terms: list[str],
    has_phrase: bool,
    has_field_prefix: bool,
    rarest_document_frequency: int,
) -> Intent:
    if not terms and not has_phrase:
        raise Invalid("an empty query has no intent to classify")
    if rarest_document_frequency < 0:
        raise Invalid("document frequency cannot be negative")
    signals: list[Signal] = []
    votes = {"navigational": 0, "lookup": 0, "exploratory": 0}

    if has_phrase or has_field_prefix:
        what = "quoted phrase" if has_phrase else "field prefix"
        signals.append(
            Signal(name=what, leaning="navigational")
        )
        votes["navigational"] += 2

    lowered = [term.lower() for term in terms]
    if lowered and lowered[0] in QUESTION_WORDS:
        signals.append(
            Signal(
                name=f"question word {lowered[0]!r}",
                leaning="lookup",
            )
        )
        votes["lookup"] += 2

    if len(terms) >= 5:
        signals.append(
            Signal(
                name=f"{len(terms)} terms",
                leaning="exploratory",
            )
        )
        votes["exploratory"] += 1
    elif 0 < len(terms) <= 2:
        signals.append(
            Signal(name=f"{len(terms)} term(s)", leaning="navigational")
        )
        votes["navigational"] += 1

    if 0 < rarest_document_frequency <= 3:
        signals.append(
            Signal(
                name=(
                    f"rarest term in "
                    f"{rarest_document_frequency} document(s)"
                ),
                leaning="navigational",
            )
        )
        votes["navigational"] += 1
    elif rarest_document_frequency > 50:
        signals.append(
            Signal(
                name=(
                    f"every term common ({rarest_document_frequency}+"
                    f" documents)"
                ),
                leaning="exploratory",
            )
        )
        votes["exploratory"] += 1

    best = max(votes.items(), key=lambda pair: (pair[1], pair[0]))
    label = best[0] if best[1] > 0 else "lookup"
    if not signals:
        signals.append(
            Signal(
                name="no strong signals",
                leaning="lookup by default",
            )
        )
    return Intent(label=label, signals=tuple(signals))
