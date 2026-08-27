"""Rank fusion: rankers vote by position, and abstentions count.

Two rankers disagree constantly, lexical and links and
freshness each seeing a different best page, and reciprocal
rank fusion is the boring workhorse that combines them: each
document earns one over k plus its rank from every list that
contains it, the constant k damping the tyranny of first place
so a document ranked second and third beats one ranked first
and fortieth. The design decisions that matter are stated:
abstention is not disapproval, a list that never saw a
document contributes nothing rather than a penalty, but the
fused entry reports how many lists voted so a one-list wonder
is distinguishable from a consensus pick; and input lists must
not contain duplicates, because a ranker that lists a document
twice is casting two ballots and the fusion would launder
that into legitimacy.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

RRF_K = 60


@dataclass(frozen=True)
class FusedHit:
    external: int
    score: float
    lists_voting: int

    def line(self) -> str:
        consensus = (
            "consensus"
            if self.lists_voting > 1
            else "single-list wonder"
        )
        return (
            f"doc {self.external}: {self.score} from "
            f"{self.lists_voting} list(s) ({consensus})"
        )


def fuse(
    rankings: dict[str, list[int]], k: int = RRF_K
) -> list[FusedHit]:
    if not rankings:
        raise Invalid("fusing no rankings ranks nothing")
    if k <= 0:
        raise Invalid(
            "k must be positive; at zero the first place is a "
            "tyranny again"
        )
    for name, ranked in rankings.items():
        if len(set(ranked)) != len(ranked):
            raise Invalid(
                f"{name} lists a document twice; two ballots from "
                f"one ranker is not consensus, it is laundering"
            )
    scores: dict[int, float] = {}
    votes: dict[int, int] = {}
    for ranked in rankings.values():
        for position, doc in enumerate(ranked, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + position)
            votes[doc] = votes.get(doc, 0) + 1
    fused = [
        FusedHit(
            external=doc,
            score=round(score, 6),
            lists_voting=votes[doc],
        )
        for doc, score in scores.items()
    ]
    fused.sort(key=lambda held: (-held.score, held.external))
    return fused


def fusion_explain(
    rankings: dict[str, list[int]], doc: int, k: int = RRF_K
) -> str:
    parts = []
    total = 0.0
    for name in sorted(rankings):
        ranked = rankings[name]
        if doc in ranked:
            position = ranked.index(doc) + 1
            share = 1.0 / (k + position)
            total += share
            parts.append(
                f"{name}: rank {position} -> {round(share, 6)}"
            )
        else:
            parts.append(
                f"{name}: abstained (not a penalty)"
            )
    parts.append(f"total {round(total, 6)}")
    return "\n".join(parts)


def agreement(rankings: dict[str, list[int]], depth: int = 10) -> float:
    """Share of top-depth documents the rankers agree on."""
    if len(rankings) < 2:
        raise Invalid("agreement needs at least two rankers")
    tops = [
        set(ranked[:depth]) for ranked in rankings.values()
    ]
    shared = set.intersection(*tops)
    widest = max(len(top) for top in tops)
    if widest == 0:
        raise Invalid("every ranker returned nothing; no agreement to measure")
    return round(len(shared) / widest, 4)
