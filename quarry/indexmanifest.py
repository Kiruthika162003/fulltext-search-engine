"""The index manifest: everything a restore needs, on one page.

Restoring an index from parts requires knowing which parts, and
the manifest is that knowledge made durable: schema identity,
analyzer identity, every segment with its document count and
content digest, the tombstone total, and the manifest format
version, assembled into a canonical text whose own digest
becomes the manifest id. Verification recomputes every segment
digest against the actual data and reports per segment, because
a restore that trusts digests it never checked is a restore
that discovers corruption at query time. The manifest is
strict about format versions, reading a newer version than it
writes is refused with instructions rather than guessed at,
since a field this code does not know about might be the one
that says do not restore this.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid, Stale
from quarry.segment import Segment

FORMAT_VERSION = 2


def segment_digest(segment: Segment) -> str:
    rows = []
    for (field_name, term), postings in sorted(
        segment.postings.items()
    ):
        docs = ",".join(
            f"{row.doc}:{row.frequency}" for row in postings.rows
        )
        rows.append(f"{field_name}|{term}|{docs}")
    body = "\n".join(rows) + f"|dead:{sorted(segment.tombstones)}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SegmentRecord:
    name: str
    doc_count: int
    live_count: int
    digest: str

    def line(self) -> str:
        return (
            f"segment {self.name}: {self.live_count} live of "
            f"{self.doc_count}, digest {self.digest}"
        )


@dataclass(frozen=True)
class Manifest:
    format_version: int
    schema_identity: str
    analyzer_identity: str
    segments: tuple[SegmentRecord, ...]

    def canonical_text(self) -> str:
        lines = [
            f"format {self.format_version}",
            f"schema {self.schema_identity}",
            f"analyzer {self.analyzer_identity}",
        ]
        lines.extend(held.line() for held in self.segments)
        return "\n".join(lines)

    def manifest_id(self) -> str:
        return hashlib.sha256(
            self.canonical_text().encode("utf-8")
        ).hexdigest()[:16]

    def total_live(self) -> int:
        return sum(held.live_count for held in self.segments)


def build_manifest(
    schema_identity: str,
    analyzer_identity: str,
    segments: list[Segment],
) -> Manifest:
    if not segments:
        raise Invalid(
            "a manifest of zero segments describes nothing worth "
            "restoring"
        )
    records = tuple(
        SegmentRecord(
            name=segment.name,
            doc_count=segment.doc_count(),
            live_count=segment.live_count(),
            digest=segment_digest(segment),
        )
        for segment in sorted(
            segments, key=lambda held: held.name
        )
    )
    return Manifest(
        format_version=FORMAT_VERSION,
        schema_identity=schema_identity,
        analyzer_identity=analyzer_identity,
        segments=records,
    )


def verify_manifest(
    manifest: Manifest, segments: list[Segment]
) -> tuple[bool, str]:
    if manifest.format_version > FORMAT_VERSION:
        raise Stale(
            f"manifest format {manifest.format_version} is newer "
            f"than this reader ({FORMAT_VERSION}); upgrade before "
            f"restoring, a field this code does not know might say "
            f"do not restore"
        )
    by_name = {segment.name: segment for segment in segments}
    lines = []
    clean = True
    for record in manifest.segments:
        segment = by_name.get(record.name)
        if segment is None:
            clean = False
            lines.append(f"{record.name}: MISSING from disk")
            continue
        actual = segment_digest(segment)
        if actual != record.digest:
            clean = False
            lines.append(
                f"{record.name}: digest mismatch, manifest "
                f"{record.digest} vs actual {actual}"
            )
        else:
            lines.append(f"{record.name}: verified")
    extras = sorted(set(by_name) - {r.name for r in manifest.segments})
    for name in extras:
        clean = False
        lines.append(
            f"{name}: on disk but not in the manifest; a restore "
            f"would silently include it"
        )
    verdict = "RESTORABLE" if clean else "DO NOT RESTORE"
    lines.append(verdict)
    return clean, "\n".join(lines)
