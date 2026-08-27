"""Query normalization for analytics: one intent, one bucket.

Query analytics double-counts the same intent in a dozen
spellings: extra spaces, shuffled terms, casing, and the
was-it-quoted variant of the same words. The normalizer folds
queries into analytic keys with each fold declared: casefold,
whitespace collapse, term sort so cat dog and dog cat share a
bucket because term order rarely changes intent in bag-of-words
search, and analyzer folding so kettles and kettle merge the
way the index already merges them. What it deliberately does
NOT fold is stated with the same weight: phrases keep their
quotes and their word order because a phrase IS its order, and
field prefixes survive because title:cat and body:cat are
different intents that happen to share letters. The fold
report says how many raw spellings each bucket absorbed, and
the top buckets after folding are the real demand, which is
the number query analytics existed to find.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import Analyzer


def normalize(text: str, analyzer: Analyzer | None = None) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        raise Invalid("an empty query normalizes to nothing")
    analyzer = analyzer or Analyzer()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        inner = " ".join(
            analyzer.terms(cleaned[1:-1])
        )
        return f'"{inner}"'
    pieces = []
    for piece in cleaned.split():
        if ":" in piece:
            field_name, _, term = piece.partition(":")
            analyzed = analyzer.terms(term)
            if analyzed:
                pieces.append(
                    f"{field_name.lower()}:{analyzed[0]}"
                )
            continue
        analyzed = analyzer.terms(piece)
        if analyzed:
            pieces.append(analyzed[0])
    if not pieces:
        raise Invalid(
            f"{text!r} normalized to nothing; every term was a "
            f"stopword or punctuation"
        )
    pieces.sort()
    return " ".join(pieces)


@dataclass
class FoldLedger:
    buckets: dict[str, list[str]] = field(default_factory=dict)

    def fold(self, raw: str) -> str:
        key = normalize(raw)
        held = self.buckets.setdefault(key, [])
        if raw not in held:
            held.append(raw)
        return key

    def demand(self, top_n: int = 5) -> list[str]:
        if not self.buckets:
            raise Invalid("no queries folded; demand is unknown")
        ranked = sorted(
            self.buckets.items(),
            key=lambda pair: (-len(pair[1]), pair[0]),
        )
        return [
            f"{key}: {len(spellings)} spelling(s)"
            for key, spellings in ranked[:top_n]
        ]

    def absorption_report(self) -> str:
        if not self.buckets:
            return "nothing folded yet"
        raw_total = sum(
            len(spellings) for spellings in self.buckets.values()
        )
        folded = raw_total - len(self.buckets)
        return (
            f"{raw_total} raw spelling(s) folded into "
            f"{len(self.buckets)} bucket(s); {folded} duplicate "
            f"intent(s) unmasked"
        )
