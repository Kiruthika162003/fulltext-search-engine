"""Persistence: an index on disk is a claim the loader must verify.

The dump writes everything the index knows into one plain structure:
schema identity, segments with their postings and tombstones, the
id map, the counters. The loader rebuilds and then audits before
handing the index back: the schema identity must match what the
caller expects, every location must point inside a real segment,
and every posting list must still be sorted, because disk is where
other programs, older versions, and hand editors live, and trusting
a file because we probably wrote it is how indexes go quietly
insane. A failed audit names the first inconsistency and refuses
the whole load, since a partially trusted index is worse than none.
"""

from __future__ import annotations

from quarry.errors import Invalid, Stale
from quarry.postings import PostingList
from quarry.schema import Schema
from quarry.segment import Segment
from quarry.writer import Index

FORMAT_VERSION = 1


def dump(index: Index) -> dict:
    return {
        "format": FORMAT_VERSION,
        "schema_identity": index.schema.identity(),
        "next_id": index.next_id,
        "next_segment": index.next_segment,
        "locations": {
            str(external): [name, local]
            for external, (name, local) in index.locations.items()
        },
        "segments": [
            {
                "name": segment.name,
                "stored": segment.stored,
                "lengths": segment.lengths,
                "tombstones": sorted(segment.tombstones),
                "postings": [
                    {
                        "field": field_name,
                        "term": term,
                        "rows": [
                            [posting.doc, list(posting.positions)]
                            for posting in held.rows
                        ],
                    }
                    for (field_name, term), held in sorted(
                        segment.postings.items()
                    )
                ],
            }
            for segment in index.segments
        ],
    }


def load(payload: dict, schema: Schema) -> Index:
    if payload.get("format") != FORMAT_VERSION:
        raise Stale(
            f"format {payload.get('format')} is not format "
            f"{FORMAT_VERSION}; migrate before loading"
        )
    if payload["schema_identity"] != schema.identity():
        raise Invalid(
            "the index was written under a different schema; querying "
            "it with this one would split the vocabulary"
        )
    index = Index(schema=schema)
    index.next_id = payload["next_id"]
    index.next_segment = payload["next_segment"]
    for row in payload["segments"]:
        postings = {}
        for entry in row["postings"]:
            held = PostingList(term=entry["term"])
            for doc, positions in entry["rows"]:
                held.add(doc, tuple(positions))
            postings[(entry["field"], entry["term"])] = held
        segment = Segment(
            name=row["name"],
            schema=schema,
            postings=postings,
            stored=row["stored"],
            lengths={k: list(v) for k, v in row["lengths"].items()},
            tombstones=set(row["tombstones"]),
        )
        index.segments.append(segment)
    index.locations = {
        int(external): (name, local)
        for external, (name, local) in payload["locations"].items()
    }
    _audit(index)
    return index


def _audit(index: Index) -> None:
    names = {segment.name for segment in index.segments}
    for external, (name, local) in sorted(index.locations.items()):
        if name not in names:
            raise Invalid(
                f"id {external} points at segment {name}, which does "
                f"not exist in this dump"
            )
        segment = next(s for s in index.segments if s.name == name)
        if not 0 <= local < segment.doc_count():
            raise Invalid(
                f"id {external} points at {name}:{local}, outside the "
                f"segment's {segment.doc_count()} documents"
            )
    for segment in index.segments:
        for (field_name, term), held in segment.postings.items():
            docs = held.docs()
            if docs != sorted(set(docs)):
                raise Invalid(
                    f"{segment.name} {field_name}:{term} lost its "
                    f"sort order on disk"
                )
        for doc in segment.tombstones:
            if not 0 <= doc < segment.doc_count():
                raise Invalid(
                    f"{segment.name} holds a tombstone for {doc}, "
                    f"which never existed"
                )
