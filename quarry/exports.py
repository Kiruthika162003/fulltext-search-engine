"""Exporting: the corpus leaves as rows, resumably, with a manifest.

Downstream systems want documents as a stream of flat rows, not a
full-fidelity index dump, and the exporter's obligations are the
boring ones that matter at three in the morning. Field selection
is explicit, asking for a field the schema lacks fails at the
start instead of producing a million rows of nulls. The stream is
resumable by external id cursor, so a consumer that died at row
seven hundred thousand resumes there rather than at zero, and
the ordering is ascending id precisely so the cursor means
something. Tombstoned documents never export. And every completed
export ends with a manifest row carrying the count and the id
range, because a file that just stops and a file that finished
look identical without one, and the difference is a page at three
in the morning.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.writer import Index

BATCH = 500


@dataclass(frozen=True)
class ExportRow:
    external: int
    fields: dict[str, object]


@dataclass(frozen=True)
class ExportBatch:
    rows: tuple[ExportRow, ...]
    cursor: int | None
    manifest: str | None

    def finished(self) -> bool:
        return self.manifest is not None


def export_batch(
    index: Index,
    fields: tuple[str, ...],
    after: int = -1,
    batch: int = BATCH,
) -> ExportBatch:
    if not fields:
        raise Invalid("an export of no fields is a count with extra steps")
    if batch <= 0:
        raise Invalid("a batch of zero exports forever")
    for name in fields:
        index.schema.get(name)
    index.flush()
    live: list[tuple[int, dict[str, object]]] = []
    for external in sorted(index.locations):
        if external <= after:
            continue
        segment_name, local = index.locations[external]
        segment = next(
            held for held in index.segments if held.name == segment_name
        )
        if not segment.is_live(local):
            continue
        live.append((external, segment.stored[local]))
        if len(live) > batch:
            break
    page = live[:batch]
    rows = tuple(
        ExportRow(
            external=external,
            fields={
                name: document.get(name) for name in fields
            },
        )
        for external, document in page
    )
    exhausted = len(live) <= batch
    if exhausted:
        first = rows[0].external if rows else None
        last = rows[-1].external if rows else None
        manifest = (
            f"export complete: {len(rows)} row(s) this batch, ids "
            f"{first}..{last}"
            if rows
            else "export complete: 0 row(s) this batch"
        )
        return ExportBatch(rows=rows, cursor=None, manifest=manifest)
    return ExportBatch(
        rows=rows, cursor=rows[-1].external, manifest=None
    )


def export_all(
    index: Index, fields: tuple[str, ...], batch: int = BATCH
) -> tuple[list[ExportRow], int]:
    """Drive the cursor to the end; rows plus the batch count."""
    rows: list[ExportRow] = []
    cursor = -1
    batches = 0
    while True:
        page = export_batch(index, fields, after=cursor, batch=batch)
        rows.extend(page.rows)
        batches += 1
        if page.finished():
            return rows, batches
        cursor = page.cursor
