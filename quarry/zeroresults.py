"""Zero-result triage: the queries that found nothing, sorted by why.

The zero-result log is the most valuable file search produces
and the least read, because raw it is thousands of lines of
noise. Triage sorts each dead query into the bucket that names
its fix: vocabulary misses, where no analyzed term exists in
the index, want content or synonyms; near misses, where terms
exist but never together, want the AND loosened toward
minimum-should-match; over-filtering, where the text matched
and a filter killed it, wants the filter surfaced to the user;
and typo candidates, where a term sits one slip from a real
one, want the corrector wired in. Buckets are checked in that
order and the first hit wins, because a query can smell of
several and shipping one clear diagnosis beats shipping a
committee. The digest ranks buckets by body count so the week's
engineering goes where the bodies are.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

BUCKETS = (
    "vocabulary-miss",
    "near-miss",
    "over-filtered",
    "typo-candidate",
    "unexplained",
)

FIXES = {
    "vocabulary-miss": "wants content or a synonym ring",
    "near-miss": "wants minimum-should-match instead of AND",
    "over-filtered": "wants the killing filter surfaced",
    "typo-candidate": "wants the corrector wired in",
    "unexplained": "wants a human to look",
}


@dataclass(frozen=True)
class DeadQuery:
    text: str
    terms_in_index: int
    terms_total: int
    matched_before_filters: bool
    one_slip_from_vocabulary: bool

    def __post_init__(self) -> None:
        if self.terms_total <= 0:
            raise Invalid(
                f"{self.text!r}: a query with no terms did not "
                f"die, it never lived"
            )
        if self.terms_in_index > self.terms_total:
            raise Invalid(
                f"{self.text!r}: more terms in the index than in "
                f"the query is arithmetic that cannot happen"
            )


def diagnose(dead: DeadQuery) -> str:
    if dead.terms_in_index == 0:
        if dead.one_slip_from_vocabulary:
            return "typo-candidate"
        return "vocabulary-miss"
    if dead.matched_before_filters:
        return "over-filtered"
    if dead.terms_in_index < dead.terms_total:
        if dead.one_slip_from_vocabulary:
            return "typo-candidate"
        return "vocabulary-miss"
    return "near-miss"


@dataclass
class TriageDesk:
    diagnosed: dict[str, list[str]] = field(default_factory=dict)

    def submit(self, dead: DeadQuery) -> str:
        bucket = diagnose(dead)
        self.diagnosed.setdefault(bucket, []).append(dead.text)
        return f"{dead.text!r}: {bucket}, {FIXES[bucket]}"

    def digest(self) -> str:
        if not self.diagnosed:
            return "no dead queries triaged; either great or unread"
        total = sum(
            len(texts) for texts in self.diagnosed.values()
        )
        ranked = sorted(
            self.diagnosed.items(),
            key=lambda pair: (-len(pair[1]), pair[0]),
        )
        lines = [f"{total} dead quer(ies) triaged:"]
        for bucket, texts in ranked:
            share = len(texts) / total
            sample = texts[0]
            lines.append(
                f"  {bucket}: {len(texts)} ({share:.0%}), e.g. "
                f"{sample!r}; {FIXES[bucket]}"
            )
        lines.append(
            f"the week's engineering goes to {ranked[0][0]}"
        )
        return "\n".join(lines)
