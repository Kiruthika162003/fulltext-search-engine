"""Noisy counts: aggregate honesty without individual disclosure.

Publishing exact query counts leaks: a term counted 1 in the
public dashboard is one identifiable person's search. The
counter answers aggregates with three privacy layers stated in
its output. Terms under the crowd floor are suppressed
entirely, reported as a bucket total so the arithmetic still
closes without naming the rare terms; surviving counts are
rounded to the declared grain because a count of 1042 versus
1041 is one person's difference; and the deterministic jitter,
a hash-seeded offset within the grain, breaks the join attack
where two dashboards published a grain apart reveal the exact
count between them. The offsets are deterministic per term and
period on purpose: real randomness would let repeated queries
average the noise away, while a fixed offset gives the same
answer every time and leaks nothing new on the second look.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid

CROWD_FLOOR = 10
GRAIN = 10


def _jitter(term: str, period: str) -> int:
    digest = hashlib.sha256(
        f"{term}|{period}".encode()
    ).digest()
    return digest[0] % GRAIN - GRAIN // 2


@dataclass(frozen=True)
class NoisyReport:
    published: dict[str, int]
    suppressed_terms: int
    suppressed_total: int

    def page(self, period: str) -> str:
        lines = [f"period {period}:"]
        for term in sorted(self.published):
            lines.append(f"  {term}: ~{self.published[term]}")
        lines.append(
            f"  (small crowds: {self.suppressed_terms} term(s) "
            f"totaling ~{self.suppressed_total}, names withheld)"
        )
        lines.append(
            f"counts rounded to {GRAIN}, crowds under "
            f"{CROWD_FLOOR} withheld"
        )
        return "\n".join(lines)


def publish(
    counts: dict[str, int], period: str
) -> NoisyReport:
    if not period.strip():
        raise Invalid(
            "a report without a period cannot be compared or "
            "retracted; name it"
        )
    for term, count in counts.items():
        if count < 0:
            raise Invalid(
                f"{term}: a negative count is a counting bug"
            )
    published: dict[str, int] = {}
    suppressed_terms = 0
    suppressed_total = 0
    for term, count in counts.items():
        if count < CROWD_FLOOR:
            suppressed_terms += 1
            suppressed_total += count
            continue
        noisy = count + _jitter(term, period)
        rounded = max(GRAIN, round(noisy / GRAIN) * GRAIN)
        published[term] = rounded
    suppressed_rounded = (
        round(suppressed_total / GRAIN) * GRAIN
        if suppressed_total
        else 0
    )
    return NoisyReport(
        published=published,
        suppressed_terms=suppressed_terms,
        suppressed_total=suppressed_rounded,
    )


def stable_across_reads(
    counts: dict[str, int], period: str, reads: int = 5
) -> bool:
    """Repeated publication must not let noise average away."""
    if reads < 2:
        raise Invalid("stability needs at least two reads")
    first = publish(counts, period).published
    return all(
        publish(counts, period).published == first
        for _ in range(reads - 1)
    )
