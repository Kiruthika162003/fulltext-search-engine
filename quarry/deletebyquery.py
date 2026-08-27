"""Delete by query: the chainsaw gets a viewfinder and a two-step trigger.

Deleting everything a query matches is the most destructive verb a
search engine owns, and the interface here is shaped by every
postmortem that starts with "the query matched more than we
thought". The dry run is mandatory: preview returns the count and
a sample of what would die, and the deletion call demands the
count from a preview as its confirmation argument, refusing when
reality has drifted from what the caller last looked at, because
deleting 40,000 documents on the strength of a preview that said
40 is the exact accident this dance exists to prevent. A guard
ceiling refuses single deletions past a declared share of the
corpus regardless of confirmation, since "delete 96 percent of
everything" is a reindex wearing a delete's clothes and deserves
the reindex machinery, checkpoints and all.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.searcher import match_group
from quarry.writer import Index

GUARD_SHARE = 0.5
SAMPLE = 5


@dataclass(frozen=True)
class DeletePreview:
    would_die: int
    corpus: int
    sample: tuple[int, ...]

    def share(self) -> float:
        if self.corpus == 0:
            raise Invalid("a share of an empty corpus is a shrug")
        return round(self.would_die / self.corpus, 4)


def _matching_externals(index: Index, query: Query) -> list[int]:
    index.flush()
    found: list[int] = []
    for segment in index.segments:
        matched: set[int] = set()
        for group in query.groups:
            matched.update(match_group(segment, group))
        for doc in sorted(matched):
            if segment.is_live(doc):
                found.append(index.external_id(segment.name, doc))
    return sorted(found)


def preview(index: Index, query: Query) -> DeletePreview:
    externals = _matching_externals(index, query)
    return DeletePreview(
        would_die=len(externals),
        corpus=index.searchable_count(),
        sample=tuple(externals[:SAMPLE]),
    )


def delete_by_query(
    index: Index,
    query: Query,
    confirmed_count: int,
    guard_share: float = GUARD_SHARE,
) -> list[int]:
    if not 0.0 < guard_share <= 1.0:
        raise Invalid("the guard share is a fraction over zero")
    externals = _matching_externals(index, query)
    if len(externals) != confirmed_count:
        raise Invalid(
            f"the corpus moved: the preview said {confirmed_count}, "
            f"reality says {len(externals)}; look again before "
            f"pulling"
        )
    corpus = index.searchable_count()
    if corpus and len(externals) / corpus > guard_share:
        raise Invalid(
            f"this would delete {len(externals)} of {corpus} "
            f"documents, past the {guard_share:.0%} guard; a deletion "
            f"that size is a reindex wearing a delete's clothes"
        )
    for external in externals:
        index.delete(external)
    return externals
