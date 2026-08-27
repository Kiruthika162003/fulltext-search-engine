"""Curation: humans overrule ranking, visibly, per query, on the record.

Some queries are merchandise: the launch page must top its own
product name this week whatever BM25 thinks. A curation pins
documents to the top of one canonical query and blocks others
from it entirely, and three rules keep this honest. The override
is per canonical query, never global, because a document pinned
for every query is a banner ad wearing a search result's
clothes. Every curation names its author and reason, so the odd
ranking a month later can be traced to a decision instead of a
bug hunt. And applying a curation marks each moved hit as
curated, because a pinned result presented as an organic one
lies to the user and, eventually, to the analyst reading the
click logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass(frozen=True)
class Curation:
    canonical: str
    pinned: tuple[int, ...]
    blocked: tuple[int, ...]
    author: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise Invalid(
                "a curation with no reason is a bug hunt scheduled "
                "for next month; say why"
            )
        overlap = set(self.pinned) & set(self.blocked)
        if overlap:
            shown = ", ".join(str(doc) for doc in sorted(overlap))
            raise Invalid(
                f"document(s) {shown} are both pinned and blocked; "
                f"pick a side"
            )

    def describe(self) -> str:
        return (
            f"{self.canonical!r}: pin {list(self.pinned)}, block "
            f"{list(self.blocked)} ({self.author}: {self.reason})"
        )


@dataclass(frozen=True)
class CuratedHit:
    external: int
    score: float
    curated: bool


@dataclass
class CurationDesk:
    curations: dict[str, Curation] = field(default_factory=dict)
    applications: int = 0

    def declare(self, curation: Curation) -> None:
        self.curations[curation.canonical] = curation

    def withdraw(self, canonical: str) -> Curation:
        held = self.curations.pop(canonical, None)
        if held is None:
            raise Missing(
                f"no curation for {canonical!r}; withdrawing what is "
                f"not there usually means the canonical form drifted"
            )
        return held

    def apply(
        self, canonical: str, ranked: list[tuple[int, float]]
    ) -> list[CuratedHit]:
        held = self.curations.get(canonical)
        if held is None:
            return [
                CuratedHit(external=doc, score=score, curated=False)
                for doc, score in ranked
            ]
        self.applications += 1
        blocked = set(held.blocked)
        organic = [
            (doc, score)
            for doc, score in ranked
            if doc not in blocked and doc not in held.pinned
        ]
        top_score = ranked[0][1] if ranked else 1.0
        out = [
            CuratedHit(external=doc, score=top_score, curated=True)
            for doc in held.pinned
        ]
        out.extend(
            CuratedHit(external=doc, score=score, curated=False)
            for doc, score in organic
        )
        return out

    def ledger(self) -> str:
        if not self.curations:
            return "no curations standing"
        lines = [
            held.describe()
            for _, held in sorted(self.curations.items())
        ]
        lines.append(
            f"{len(self.curations)} standing, applied "
            f"{self.applications} time(s)"
        )
        return "\n".join(lines)
