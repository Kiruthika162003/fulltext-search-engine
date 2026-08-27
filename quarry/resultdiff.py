"""Result diffing: what a ranking change actually did, named per query.

Every relevance change ships with a fear: what moved that should
not have. The diff answers with arithmetic instead of vibes. For
one query it aligns the before and after lists and reports
entries, exits, and moves with their positions; across a suite
it aggregates into churn, the share of top slots that changed
hands, and flags the queries that changed most, because a
harmless average hides the one query that inverted. Rank
correlation is measured on the shared documents with the
standard footrule distance, stated as a fraction of its own
worst case so 0 means untouched and 1 means reversed, and a
query whose results vanished entirely is listed by name rather
than averaged into the fog.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid


@dataclass(frozen=True)
class Move:
    doc: int
    before: int | None
    after: int | None

    def line(self) -> str:
        if self.before is None:
            return f"doc {self.doc}: entered at {self.after}"
        if self.after is None:
            return f"doc {self.doc}: exited from {self.before}"
        arrowless = "up" if self.after < self.before else "down"
        return (
            f"doc {self.doc}: {arrowless} from {self.before} "
            f"to {self.after}"
        )


@dataclass(frozen=True)
class QueryDiff:
    canonical: str
    moves: tuple[Move, ...]
    disorder: float

    def stable(self) -> bool:
        return not self.moves

    def summary(self) -> str:
        if self.stable():
            return f"{self.canonical!r}: unchanged"
        entered = sum(1 for m in self.moves if m.before is None)
        exited = sum(1 for m in self.moves if m.after is None)
        moved = len(self.moves) - entered - exited
        return (
            f"{self.canonical!r}: {entered} entered, {exited} "
            f"exited, {moved} moved, disorder {self.disorder}"
        )


def diff_query(
    canonical: str, before: list[int], after: list[int]
) -> QueryDiff:
    if len(set(before)) != len(before) or len(set(after)) != len(after):
        raise Invalid(
            f"{canonical!r}: a ranking with a repeated document is "
            f"already broken; diffing it would bless the breakage"
        )
    before_pos = {doc: pos for pos, doc in enumerate(before)}
    after_pos = {doc: pos for pos, doc in enumerate(after)}
    moves = []
    for doc in before:
        if doc not in after_pos:
            moves.append(
                Move(doc=doc, before=before_pos[doc], after=None)
            )
        elif after_pos[doc] != before_pos[doc]:
            moves.append(
                Move(
                    doc=doc,
                    before=before_pos[doc],
                    after=after_pos[doc],
                )
            )
    for doc in after:
        if doc not in before_pos:
            moves.append(
                Move(doc=doc, before=None, after=after_pos[doc])
            )
    shared = [doc for doc in before if doc in after_pos]
    disorder = _footrule(shared, before_pos, after_pos)
    return QueryDiff(
        canonical=canonical,
        moves=tuple(moves),
        disorder=disorder,
    )


def _footrule(
    shared: list[int],
    before_pos: dict[int, int],
    after_pos: dict[int, int],
) -> float:
    """Spearman footrule over shared docs, scaled to its worst case."""
    if len(shared) < 2:
        return 0.0
    before_rank = {
        doc: rank for rank, doc in enumerate(shared)
    }
    after_rank = {
        doc: rank
        for rank, doc in enumerate(
            sorted(shared, key=lambda held: after_pos[held])
        )
    }
    distance = sum(
        abs(before_rank[doc] - after_rank[doc]) for doc in shared
    )
    half = len(shared) // 2
    worst = 2 * half * (len(shared) - half)
    return round(distance / worst, 4)


@dataclass(frozen=True)
class SuiteDiff:
    diffs: tuple[QueryDiff, ...]

    def churn(self) -> float:
        if not self.diffs:
            raise Invalid("a suite of no queries has no churn")
        changed = sum(1 for held in self.diffs if not held.stable())
        return round(changed / len(self.diffs), 4)

    def noisiest(self, top_n: int = 3) -> list[QueryDiff]:
        ranked = sorted(
            self.diffs,
            key=lambda held: (-held.disorder, -len(held.moves)),
        )
        return [held for held in ranked[:top_n] if not held.stable()]

    def emptied(self) -> list[str]:
        return [
            held.canonical
            for held in self.diffs
            if held.moves
            and all(move.after is None for move in held.moves)
        ]

    def report(self) -> str:
        lines = [
            f"churn: {self.churn():.0%} of {len(self.diffs)} "
            f"queries changed"
        ]
        for held in self.noisiest():
            lines.append(f"  {held.summary()}")
        for name in self.emptied():
            lines.append(f"  {name!r}: RESULTS VANISHED")
        return "\n".join(lines)
