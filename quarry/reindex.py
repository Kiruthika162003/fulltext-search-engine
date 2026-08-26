"""Reindexing: the new index earns the alias before anyone meets it.

Changing an analyzer or schema means building a second index and
moving the alias, and the choreography here is the whole safety
story. Dual writes start first, so every document added during the
rebuild lands in both worlds and the new index never misses the
news. The backfill then copies the old corpus through the new
schema, batch by batch with progress reported. The verification
gate runs before any swap: document counts must reconcile, and a
caller-supplied set of probe queries must return the same external
ids from both indexes, because counts matching while queries
diverge is exactly how analyzer bugs ship. Only a verified rebuild
may swap, the swap is the atomic alias move, and the old index
stays registered for the rollback nobody plans and somebody needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.aliases import AliasTable
from quarry.errors import Invalid
from quarry.multisearch import search_index
from quarry.query import parse


@dataclass
class Reindex:
    table: AliasTable
    alias: str
    old_name: str
    new_name: str
    batch: int = 100
    dual_writing: bool = False
    backfilled: int = 0
    verified: bool = False
    id_map: dict[int, int] = field(default_factory=dict)

    def begin_dual_writes(self) -> None:
        if self.dual_writing:
            raise Invalid("dual writes already began")
        self.dual_writing = True

    def add(self, document: dict[str, object]) -> tuple[int, int]:
        """The write path during the migration: both worlds, always."""
        if not self.dual_writing:
            raise Invalid(
                "writes during a reindex must be dual; begin them first"
            )
        old_id = self.table.indexes[self.old_name].add(document)
        new_id = self.table.indexes[self.new_name].add(document)
        self.id_map[old_id] = new_id
        return old_id, new_id

    def backfill(self) -> int:
        """Copy the old corpus through the new schema, in batches."""
        old = self.table.indexes[self.old_name]
        new = self.table.indexes[self.new_name]
        old.flush()
        copied = 0
        for segment in old.segments:
            for local in range(segment.doc_count()):
                if not segment.is_live(local):
                    continue
                external = old.external_id(segment.name, local)
                if external in self.id_map:
                    continue
                new_id = new.add(dict(segment.stored[local]))
                self.id_map[external] = new_id
                copied += 1
                if copied % self.batch == 0:
                    new.flush()
        new.flush()
        self.backfilled += copied
        return copied

    def verify(self, probe_queries: list[str]) -> list[str]:
        """Counts must reconcile and probes must agree; failures listed."""
        if not probe_queries:
            raise Invalid(
                "verification without probes is a count with a costume; "
                "supply the queries that matter"
            )
        old = self.table.indexes[self.old_name]
        new = self.table.indexes[self.new_name]
        old.flush()
        new.flush()
        complaints = []
        if old.searchable_count() != new.searchable_count():
            complaints.append(
                f"counts diverge: old {old.searchable_count()}, new "
                f"{new.searchable_count()}"
            )
        for text in probe_queries:
            query = parse(text)
            old_ids = {
                self.id_map.get(hit.external)
                for hit in search_index(old, query, limit=100).hits
            }
            new_ids = {
                hit.external
                for hit in search_index(new, query, limit=100).hits
            }
            if old_ids != new_ids:
                complaints.append(
                    f"probe {text!r} diverges: old maps to "
                    f"{sorted(old_ids)}, new returns {sorted(new_ids)}"
                )
        self.verified = not complaints
        return complaints

    def swap(self, who: str) -> None:
        if not self.verified:
            raise Invalid(
                "swap refused: this rebuild never passed verification, "
                "and hope is not a gate"
            )
        self.table.point(
            self.alias,
            self.new_name,
            who=who,
            reason=f"reindex {self.old_name} -> {self.new_name}, "
            f"{self.backfilled} backfilled, probes green",
        )

    def rollback(self, who: str, reason: str) -> None:
        self.table.point(
            self.alias, self.old_name, who=who, reason=reason
        )
