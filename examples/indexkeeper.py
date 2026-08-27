"""A keeper's shift: manifest, journal, pressure, drills, verdicts.

Run with: python -m examples.indexkeeper
"""

from __future__ import annotations

from quarry.backpressure import Backpressure
from quarry.chaosdrill import Drill, DrillBook
from quarry.indexmanifest import build_manifest, verify_manifest
from quarry.journal import Journal
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.upgradecheck import (
    check_format,
    check_journal,
    check_segments,
    preflight,
)


def overnight_segments() -> list[Segment]:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    segments = []
    for name, texts in (
        ("night-1", ["the harbor ledger", "a quiet cove"]),
        ("night-2", ["rain on the wall", "the long walk home"]),
    ):
        builder = SegmentBuilder(schema=schema)
        for text in texts:
            builder.add({"body": text})
        segments.append(builder.seal(name))
    return segments


def main() -> int:
    segments = overnight_segments()
    manifest = build_manifest("body", "lower=1|stop=1|stem=1", segments)
    clean, page = verify_manifest(manifest, segments)
    print(f"manifest {manifest.manifest_id()}: {page.splitlines()[-1]}")

    journal = Journal()
    journal.append("add", "doc:4 the morning batch")
    journal.append("add", "doc:5 arrives before flush")
    journal.mark_checkpoint(0)
    kept, verdict = journal.replay()
    print(f"journal: {verdict}")

    pressure = Backpressure(capacity=10)
    for _ in range(6):
        pressure.admit(urgent=True)
    print(pressure.flush(drained=4))

    book = DrillBook()

    def tampered_manifest() -> str:
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "the harbor ledger, edited"})
        impostor = builder.seal("night-1")
        ok, _ = verify_manifest(manifest, [impostor, segments[1]])
        if ok:
            raise RuntimeError("tampering passed verification")
        return "tampering caught by digest"

    book.schedule(Drill("tampered-manifest", tampered_manifest))
    book.run_all()
    print(book.report().splitlines()[-1])

    checks = [
        check_format(2, readable_min=1, readable_max=3),
        check_segments(clean),
        check_journal(pending_entries=len(kept)),
    ]
    print(preflight(checks).splitlines()[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
