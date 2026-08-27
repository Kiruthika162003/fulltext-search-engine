"""Boolean simplification: the query means the same, costs less.

Machine-built queries arrive bloated: duplicate clauses from
template concatenation, OR branches subsumed by wider siblings,
double negations from UI toggles toggled twice. The optimizer
rewrites to a cheaper equivalent and proves each rule by name:
duplicate clauses within a group collapse because AND is
idempotent, a group repeated across OR collapses because OR is
too, an OR branch strictly containing another branch's clauses
is dropped because the narrower branch already implies it
matches whenever the wider would, and a group that requires
and prohibits the same term is deleted as unsatisfiable with
the deletion reported, since silently keeping a
never-matching branch wastes a traversal per query forever.
Every rewrite is listed in the report by rule name, and a
query that needed nothing says so, because an optimizer whose
silence is ambiguous gets blamed for every odd result.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Clause, Query


def _clause_key(clause: Clause) -> tuple[str, str, str, bool, bool]:
    return (
        clause.kind,
        clause.field,
        clause.text,
        clause.required,
        clause.prohibited,
    )


def _group_key(group: tuple[Clause, ...]) -> tuple:
    return tuple(sorted(_clause_key(clause) for clause in group))


def _unsatisfiable(group: tuple[Clause, ...]) -> bool:
    required = {
        (clause.field, clause.text)
        for clause in group
        if not clause.prohibited
    }
    prohibited = {
        (clause.field, clause.text)
        for clause in group
        if clause.prohibited
    }
    return bool(required & prohibited)


@dataclass(frozen=True)
class Simplified:
    query: Query
    rewrites: tuple[str, ...]

    def report(self) -> str:
        if not self.rewrites:
            return "already minimal; nothing rewritten"
        return "\n".join(self.rewrites)


def simplify(query: Query) -> Simplified:
    rewrites: list[str] = []
    groups: list[tuple[Clause, ...]] = []

    for index, group in enumerate(query.groups):
        seen: set[tuple] = set()
        kept: list[Clause] = []
        for clause in group:
            key = _clause_key(clause)
            if key in seen:
                rewrites.append(
                    f"group {index}: duplicate clause "
                    f"{clause.canonical()} collapsed (AND is "
                    f"idempotent)"
                )
                continue
            seen.add(key)
            kept.append(clause)
        cleaned = tuple(kept)
        if _unsatisfiable(cleaned):
            rewrites.append(
                f"group {index}: requires and prohibits the same "
                f"term; deleted as unsatisfiable"
            )
            continue
        groups.append(cleaned)

    if not groups:
        raise Invalid(
            "every branch was unsatisfiable; this query can never "
            "match and should not run"
        )

    unique: list[tuple[Clause, ...]] = []
    seen_groups: set[tuple] = set()
    for group in groups:
        key = _group_key(group)
        if key in seen_groups:
            rewrites.append(
                "duplicate OR branch collapsed (OR is idempotent)"
            )
            continue
        seen_groups.add(key)
        unique.append(group)

    survivors: list[tuple[Clause, ...]] = []
    for group in unique:
        mine = set(_group_key(group))
        subsumed = False
        for other in unique:
            if other is group:
                continue
            theirs = set(_group_key(other))
            if theirs < mine:
                subsumed = True
                rewrites.append(
                    "an OR branch was dropped: a narrower branch "
                    "already implies it"
                )
                break
        if not subsumed:
            survivors.append(group)

    return Simplified(
        query=Query(groups=tuple(survivors)),
        rewrites=tuple(rewrites),
    )
