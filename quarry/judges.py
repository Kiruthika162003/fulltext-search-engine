"""Relevance judgments: pooled fairly, and the judges judged too.

Evals are only as good as their judgments, and judgments have two
classic failure modes: the pool was drawn from one system, which
blinds the labels to everything that system missed, and the judges
disagree more than anyone checked. Pooling here takes the top
results of every contributing system, unioned and shuffled by a
deterministic key so no judge can infer rank from order, with each
document's provenance kept for the bias audit: a pool where ninety
percent of documents came from one system is that system grading
its own homework. Agreement is Cohen's kappa on the overlap set,
chance-corrected because two judges labelling ninety percent
relevant agree constantly by accident, and the kappa bands are
stated plainly: below 0.4 the labels are noise and the eval built
on them inherits the noise.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid

KAPPA_NOISE_LINE = 0.4


@dataclass
class JudgmentPool:
    contributions: dict[str, set[int]] = field(default_factory=dict)

    def contribute(self, system: str, top_documents: list[int]) -> None:
        if not top_documents:
            raise Invalid(
                f"{system} contributed nothing; an empty run cannot "
                f"widen the pool"
            )
        self.contributions.setdefault(system, set()).update(
            top_documents
        )

    def pooled(self) -> list[int]:
        """The union, shuffled deterministically so order hides rank."""
        union: set[int] = set()
        for documents in self.contributions.values():
            union |= documents
        if not union:
            raise Invalid("an empty pool judges nothing")
        return sorted(
            union,
            key=lambda doc: hashlib.sha256(
                str(doc).encode()
            ).hexdigest(),
        )

    def provenance_audit(self) -> str:
        union = set()
        for documents in self.contributions.values():
            union |= documents
        total = len(union)
        lines = []
        homework = False
        for system in sorted(self.contributions):
            share = len(self.contributions[system]) / total
            lines.append(f"{system}: {share:.0%} of the pool")
            if share > 0.9:
                homework = True
        head = "pool provenance:"
        if homework:
            head = (
                "POOL BIAS: one system supplied over 90 percent; it "
                "is grading its own homework"
            )
        return "\n".join([head, *[f"  {line}" for line in lines]])


def cohens_kappa(
    left: dict[int, bool], right: dict[int, bool]
) -> float:
    overlap = sorted(set(left) & set(right))
    if len(overlap) < 5:
        raise Invalid(
            f"{len(overlap)} shared judgment(s) is too few to measure "
            f"agreement; assign more overlap"
        )
    agree = sum(1 for doc in overlap if left[doc] == right[doc])
    observed = agree / len(overlap)
    left_yes = sum(1 for doc in overlap if left[doc]) / len(overlap)
    right_yes = sum(1 for doc in overlap if right[doc]) / len(overlap)
    chance = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    if chance == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return round((observed - chance) / (1 - chance), 4)


def agreement_verdict(kappa: float) -> str:
    if kappa < KAPPA_NOISE_LINE:
        return (
            f"kappa {kappa}: below the noise line; these labels are "
            f"noise and any eval built on them inherits it"
        )
    if kappa < 0.7:
        return f"kappa {kappa}: usable with care; adjudicate the splits"
    return f"kappa {kappa}: solid agreement"
