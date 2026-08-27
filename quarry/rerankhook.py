"""A rerank hook: external scorers adjust the top, never the recall.

Teams bolt smarter scorers onto lexical engines, and the honest
contract for that seam is narrow: the hook receives only the top
window of already-ranked hits, returns an adjustment per hit,
and the engine reorders inside the window while everything below
it keeps its lexical order untouched, so an external model can
polish the top ten but can never resurrect a document lexical
search rejected or bury one below the window it was never shown.
Adjustments are bounded to a declared range and clipped with a
count of clips, because a hook that returns a thousand is either
broken or trying to become the ranker, and the hook is fused: a
raised exception disables it for the session and the lexical
order ships, since a broken reranker must degrade to plain
search, never to an error page.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from quarry.errors import Invalid

WINDOW = 10
ADJUST_RANGE = 2.0


@dataclass(frozen=True)
class RerankedHit:
    external: int
    lexical_score: float
    adjustment: float

    def final_score(self) -> float:
        return round(self.lexical_score + self.adjustment, 6)


@dataclass
class RerankSeam:
    hook: Callable[[list[tuple[int, float]]], dict[int, float]]
    fused: bool = False
    fuse_reason: str = ""
    clips: int = 0
    calls: int = 0

    def rerank(
        self, ranked: list[tuple[int, float]]
    ) -> list[RerankedHit]:
        if not ranked:
            raise Invalid("reranking an empty page reranks nothing")
        window = ranked[:WINDOW]
        below = ranked[WINDOW:]
        adjustments: dict[int, float] = {}
        if not self.fused:
            self.calls += 1
            try:
                adjustments = self.hook(list(window))
            except Exception as died:
                self.fused = True
                self.fuse_reason = (
                    f"{type(died).__name__}: {died}"
                )
                adjustments = {}
        strays = set(adjustments) - {doc for doc, _ in window}
        if strays:
            listed = ", ".join(str(doc) for doc in sorted(strays))
            self.fused = True
            self.fuse_reason = (
                f"adjusted document(s) {listed} outside its window"
            )
            adjustments = {}
        out = []
        for doc, score in window:
            raw = adjustments.get(doc, 0.0)
            clipped = max(-ADJUST_RANGE, min(ADJUST_RANGE, raw))
            if clipped != raw:
                self.clips += 1
            out.append(
                RerankedHit(
                    external=doc,
                    lexical_score=score,
                    adjustment=clipped,
                )
            )
        out.sort(
            key=lambda held: (-held.final_score(), held.external)
        )
        out.extend(
            RerankedHit(
                external=doc, lexical_score=score, adjustment=0.0
            )
            for doc, score in below
        )
        return out

    def status(self) -> str:
        if self.fused:
            return (
                f"FUSED after {self.calls} call(s): "
                f"{self.fuse_reason}; lexical order ships"
            )
        return (
            f"live: {self.calls} call(s), {self.clips} adjustment(s) "
            f"clipped to +/-{ADJUST_RANGE}"
        )
