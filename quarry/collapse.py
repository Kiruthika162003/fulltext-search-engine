"""Field collapsing: one hit per author, the rest fold underneath.

Search results from a prolific source elbow everything else off
the page: one newsletter with forty matching issues is forty
results the user experiences as one. Collapsing groups hits by a
key field, keeps the best-scoring representative per group in the
position its score earned, and folds the rest beneath it with a
count, so diversity comes from presentation and no document is
deleted from the ranking, only tucked. The rules that keep it
honest: the representative is the group's best scorer with ties by
id, groups never reorder around their representatives, documents
missing the collapse key form their own singleton groups rather
than one big anonymous family, and the folded count is reported
per group because "and 39 more issues" is the difference between
tidy and hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.multisearch import search_index
from quarry.query import Query
from quarry.writer import Index


@dataclass(frozen=True)
class CollapsedGroup:
    key: object | None
    representative: int
    representative_score: float
    folded: tuple[int, ...]

    def folded_count(self) -> int:
        return len(self.folded)


def collapse_search(
    index: Index,
    query: Query,
    by: str,
    limit: int = 10,
) -> list[CollapsedGroup]:
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    declared = index.schema.get(by)
    if declared.kind == "text":
        raise Invalid(
            f"{by} is analyzed text; collapsing on surviving tokens "
            f"groups by accident. Collapse on keyword or numeric "
            f"fields"
        )
    page = search_index(index, query, limit=10_000_000)
    groups: dict[object, list[tuple[int, float]]] = {}
    singleton_counter = 0
    order: list[object] = []
    for hit in page.hits:
        document = index.document(hit.external)
        key = document.get(by)
        if key is None:
            key = f"\x00singleton-{singleton_counter}"
            singleton_counter += 1
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((hit.external, hit.score))
    collapsed = []
    for key in order:
        members = groups[key]
        representative, score = members[0]
        folded = tuple(external for external, _ in members[1:])
        shown_key = (
            None if isinstance(key, str) and key.startswith("\x00") else key
        )
        collapsed.append(
            CollapsedGroup(
                key=shown_key,
                representative=representative,
                representative_score=score,
                folded=folded,
            )
        )
    return collapsed[:limit]


def collapse_report(groups: list[CollapsedGroup], by: str) -> str:
    lines = [f"collapsed by {by}: {len(groups)} group(s)"]
    for group in groups:
        shown = "(no key)" if group.key is None else str(group.key)
        tail = (
            f" and {group.folded_count()} more"
            if group.folded_count()
            else ""
        )
        lines.append(
            f"  {shown}: doc {group.representative} "
            f"({group.representative_score}){tail}"
        )
    return "\n".join(lines)
