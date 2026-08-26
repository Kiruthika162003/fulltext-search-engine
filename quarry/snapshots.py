"""Snapshots: a restore point is only real once it has restored.

A snapshot captures the index at a moment: the segment names, the
tombstones as of then, the id map, the counters. Incremental
snapshots store only segments the previous snapshot lacks, because
segments are immutable and shipping the same sealed bytes twice is
a bandwidth bill with no information in it. The catalogue chains
increments back to their base and restores by walking the chain,
and every restore verifies before handing the index over: the
chained segments must actually cover what the manifest promises,
a broken link naming the snapshot that lost it. The final rule is
cultural as much as technical: the verify-restore drill exists as
a first-class operation, because a backup that has never restored
is a rumour, and rumours fail on the day they are needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.persist import dump, load
from quarry.schema import Schema
from quarry.writer import Index


@dataclass(frozen=True)
class Manifest:
    name: str
    base: str | None
    segment_names: tuple[str, ...]
    carried_segments: tuple[str, ...]
    doc_count: int


@dataclass
class SnapshotCatalogue:
    schema: Schema
    manifests: dict[str, Manifest] = field(default_factory=dict)
    payloads: dict[str, dict] = field(default_factory=dict)
    restores_drilled: int = 0

    def take(
        self, name: str, index: Index, base: str | None = None
    ) -> Manifest:
        if name in self.manifests:
            raise Invalid(f"snapshot {name} already exists")
        if base is not None and base not in self.manifests:
            raise Missing(f"base snapshot {base} does not exist")
        index.flush()
        payload = dump(index)
        all_names = tuple(
            row["name"] for row in payload["segments"]
        )
        already_held: set[str] = set()
        if base is not None:
            already_held = set(self._chain_segments(base))
        carried = tuple(
            row["name"]
            for row in payload["segments"]
            if row["name"] not in already_held
        )
        payload["segments"] = [
            row
            for row in payload["segments"]
            if row["name"] in set(carried)
        ]
        manifest = Manifest(
            name=name,
            base=base,
            segment_names=all_names,
            carried_segments=carried,
            doc_count=index.searchable_count(),
        )
        self.manifests[name] = manifest
        self.payloads[name] = payload
        return manifest

    def _chain(self, name: str) -> list[Manifest]:
        chain = []
        cursor: str | None = name
        while cursor is not None:
            held = self.manifests.get(cursor)
            if held is None:
                raise Missing(
                    f"the chain is broken: snapshot {cursor} is gone"
                )
            chain.append(held)
            cursor = held.base
        return chain

    def _chain_segments(self, name: str) -> list[str]:
        held: list[str] = []
        for manifest in self._chain(name):
            held.extend(manifest.carried_segments)
        return held

    def restore(self, name: str) -> Index:
        if name not in self.manifests:
            raise Missing(f"no snapshot named {name}")
        manifest = self.manifests[name]
        available: dict[str, dict] = {}
        for link in self._chain(name):
            for row in self.payloads[link.name]["segments"]:
                available.setdefault(row["name"], row)
        missing = [
            segment_name
            for segment_name in manifest.segment_names
            if segment_name not in available
        ]
        if missing:
            raise Invalid(
                f"restore of {name} is impossible: the chain never "
                f"carried {', '.join(missing)}"
            )
        payload = dict(self.payloads[name])
        payload["segments"] = [
            available[segment_name]
            for segment_name in manifest.segment_names
        ]
        restored = load(payload, self.schema)
        self.restores_drilled += 1
        return restored

    def drill(self, name: str) -> str:
        """The verify-restore drill: restore, count, compare, report."""
        restored = self.restore(name)
        manifest = self.manifests[name]
        if restored.searchable_count() != manifest.doc_count:
            return (
                f"DRILL FAILED: {name} restored "
                f"{restored.searchable_count()} documents against a "
                f"manifest of {manifest.doc_count}"
            )
        return (
            f"drill passed: {name} restored {manifest.doc_count} "
            f"document(s) through a chain of {len(self._chain(name))}"
        )

    def shipping_saved(self, name: str) -> int:
        """Segments the increment did not reship, thanks to its base."""
        manifest = self.manifests[name]
        return len(manifest.segment_names) - len(
            manifest.carried_segments
        )
