"""Synonym auditing: the ring earns its place or leaves the book.

Synonym rings are written once and rot forever: the abbreviation
that stopped being used, the brand that changed hands, the pair
that was never synonymous outside one author's head. The audit
scores every declared pair against the corpus and the query
log: corpus support is how often the two terms actually share
documents, log support is whether searches for one clicked
results matching the other, and a pair failing both is flagged
for retirement with its numbers, never auto-deleted, because
synonym removal changes recall and recall changes are decisions.
The audit also hunts the inverse rot, ring transitivity gone
wrong: A joined to B and B to C silently joins A to C, and when
the corpus shows A and C never co-occur the chain is reported
as a bridge too far, the classic wreck where couch-sofa and
sofa-bed quietly teach the engine that a couch is a bed.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

CORPUS_FLOOR = 0.1
LOG_FLOOR = 0.05


@dataclass(frozen=True)
class PairEvidence:
    left: str
    right: str
    corpus_overlap: float
    log_crossover: float

    def __post_init__(self) -> None:
        for value in (self.corpus_overlap, self.log_crossover):
            if not 0.0 <= value <= 1.0:
                raise Invalid(
                    f"{self.left}-{self.right}: evidence shares "
                    f"live in [0, 1]"
                )

    def healthy(self) -> bool:
        return (
            self.corpus_overlap >= CORPUS_FLOOR
            or self.log_crossover >= LOG_FLOOR
        )

    def verdict(self) -> str:
        if self.healthy():
            return (
                f"{self.left}-{self.right}: earning its place "
                f"(corpus {self.corpus_overlap}, log "
                f"{self.log_crossover})"
            )
        return (
            f"{self.left}-{self.right}: RETIRE, corpus "
            f"{self.corpus_overlap} under {CORPUS_FLOOR} and log "
            f"{self.log_crossover} under {LOG_FLOOR}; a decision, "
            f"not an auto-delete"
        )


def audit_pairs(pairs: list[PairEvidence]) -> tuple[list[str], str]:
    if not pairs:
        raise Invalid("auditing an empty synonym book audits nothing")
    retire = [
        held.verdict() for held in pairs if not held.healthy()
    ]
    lines = [held.verdict() for held in pairs]
    summary = (
        f"{len(pairs)} pair(s) audited, {len(retire)} flagged for "
        f"retirement"
    )
    lines.append(summary)
    return retire, "\n".join(lines)


@dataclass(frozen=True)
class ChainReport:
    chain: tuple[str, ...]
    end_to_end_overlap: float

    def bridge_too_far(self) -> bool:
        return self.end_to_end_overlap < CORPUS_FLOOR / 2

    def line(self) -> str:
        route = " -> ".join(self.chain)
        if self.bridge_too_far():
            return (
                f"{route}: BRIDGE TOO FAR, the ends share "
                f"{self.end_to_end_overlap} of their documents; "
                f"the middle term joined two strangers"
            )
        return (
            f"{route}: holds, ends overlap at "
            f"{self.end_to_end_overlap}"
        )


def audit_chains(
    rings: dict[str, set[str]],
    overlap: dict[tuple[str, str], float],
) -> list[ChainReport]:
    """Two-hop chains through shared middles, judged end to end."""
    reports = []
    for middle, joined in sorted(rings.items()):
        members = sorted(joined)
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                key = (min(left, right), max(left, right))
                end_overlap = overlap.get(key)
                if end_overlap is None:
                    raise Invalid(
                        f"no overlap measured for {key[0]}-{key[1]}; "
                        f"audit with the corpus in hand"
                    )
                reports.append(
                    ChainReport(
                        chain=(left, middle, right),
                        end_to_end_overlap=end_overlap,
                    )
                )
    return reports
