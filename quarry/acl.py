"""Document security: the filter runs inside the search, never after.

Filtering results after ranking leaks through every side channel a
search engine has: the total count says how many secrets matched,
the facet counts say what kinds, and page two arrives short where
the redactions fell. So access control is a filter clause fused
into the match: documents carry grant labels, callers carry a set
of principals, and a document is visible when the two intersect.
Everything downstream, counts, facets, pagination, snippets, sees
only the visible corpus and cannot leak what it never met. Public
documents carry the public grant explicitly rather than by absence,
because a missing label being readable by everyone is the default
that ships an internal memo to the homepage.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.searcher import match_group
from quarry.writer import Index

PUBLIC = "public"
GRANT_FIELD = "granted_to"


@dataclass(frozen=True)
class Caller:
    name: str
    principals: frozenset[str]

    def __post_init__(self) -> None:
        if not self.principals:
            raise Invalid(
                f"{self.name} carries no principals; an empty badge "
                f"reads nothing, and that should be said with an empty "
                f"result, not an error five layers down"
            )


@dataclass(frozen=True)
class VisibleHit:
    external: int


@dataclass
class SecureSearcher:
    index: Index
    checks: int = 0
    denials: int = 0

    def _grants_of(self, segment_name: str, doc: int) -> set[str]:
        segment = next(
            held
            for held in self.index.segments
            if held.name == segment_name
        )
        raw = segment.stored[doc].get(GRANT_FIELD)
        if raw is None:
            return set()
        if isinstance(raw, str):
            return {raw}
        return set(raw)

    def visible_docs(self, query: Query, caller: Caller) -> list[VisibleHit]:
        found: list[VisibleHit] = []
        for segment in self.index.segments:
            matched: set[int] = set()
            for group in query.groups:
                matched.update(match_group(segment, group))
            for doc in sorted(matched):
                if not segment.is_live(doc):
                    continue
                self.checks += 1
                grants = self._grants_of(segment.name, doc)
                if not grants:
                    self.denials += 1
                    continue
                if grants & caller.principals:
                    found.append(
                        VisibleHit(
                            external=self.index.external_id(
                                segment.name, doc
                            )
                        )
                    )
                else:
                    self.denials += 1
        return found

    def visible_count(self, query: Query, caller: Caller) -> int:
        """The count the caller is allowed to know exists."""
        return len(self.visible_docs(query, caller))

    def audit_line(self) -> str:
        return (
            f"{self.checks} visibility checks, {self.denials} denials; "
            f"denied documents were never counted, faceted, or paged"
        )


def stamp_grants(
    document: dict[str, object], grants: list[str]
) -> dict[str, object]:
    """The indexing-side helper: grants are explicit or the add fails."""
    if not grants:
        raise Invalid(
            "a document with no grants is invisible forever; say "
            "public explicitly if that is what you mean"
        )
    if len(set(grants)) != len(grants):
        raise Invalid("duplicate grants; one principal, one label")
    stamped = dict(document)
    stamped[GRANT_FIELD] = list(grants)
    return stamped
