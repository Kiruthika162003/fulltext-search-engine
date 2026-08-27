"""The invariant audit: everything the index promises, checked in one sweep.

Every module trusts structural promises its neighbours keep:
postings sorted, positions climbing, lengths matching documents,
locations bijective, tombstones naming real documents. Each
promise is enforced at its own write path, but write paths have
bugs, migrations have gaps, and disks have opinions, so the audit
re-verifies everything from the outside in one sweep and reports
per invariant, because "the index is corrupt" is a panic while
"seg2 holds a tombstone for document 9 of 6" is a fix. The sweep
is read-only by construction and safe to run against a live
index, and the closing line when everything holds names the count
of checks passed rather than saying OK, since the difference
between eight-invariants-verified and OK is whether anyone can
tell the audit itself still works.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.writer import Index


@dataclass(frozen=True)
class Violation:
    invariant: str
    detail: str


def audit_index(index: Index) -> list[Violation]:
    violations: list[Violation] = []
    checks = 0

    checks += 1
    for segment in index.segments:
        for (field_name, term), postings in segment.postings.items():
            docs = postings.docs()
            if docs != sorted(set(docs)):
                violations.append(
                    Violation(
                        invariant="postings-sorted",
                        detail=(
                            f"{segment.name} {field_name}:{term} "
                            f"lost its doc order"
                        ),
                    )
                )

    checks += 1
    for segment in index.segments:
        for (field_name, term), postings in segment.postings.items():
            for posting in postings.rows:
                positions = list(posting.positions)
                if positions != sorted(set(positions)):
                    violations.append(
                        Violation(
                            invariant="positions-climbing",
                            detail=(
                                f"{segment.name} {field_name}:{term} "
                                f"doc {posting.doc} positions fell over"
                            ),
                        )
                    )

    checks += 1
    for segment in index.segments:
        for field_name, lengths in segment.lengths.items():
            if len(lengths) != segment.doc_count():
                violations.append(
                    Violation(
                        invariant="lengths-cover-documents",
                        detail=(
                            f"{segment.name} {field_name}: "
                            f"{len(lengths)} lengths for "
                            f"{segment.doc_count()} documents"
                        ),
                    )
                )

    checks += 1
    seen_addresses: dict[tuple[str, int], int] = {}
    for external, (segment_name, local) in index.locations.items():
        address = (segment_name, local)
        if address in seen_addresses:
            violations.append(
                Violation(
                    invariant="locations-bijective",
                    detail=(
                        f"ids {seen_addresses[address]} and "
                        f"{external} share address "
                        f"{segment_name}:{local}"
                    ),
                )
            )
        seen_addresses[address] = external

    checks += 1
    names = {segment.name for segment in index.segments}
    for external, (segment_name, local) in index.locations.items():
        if segment_name not in names:
            violations.append(
                Violation(
                    invariant="locations-resolve",
                    detail=(
                        f"id {external} points at missing segment "
                        f"{segment_name}"
                    ),
                )
            )
            continue
        segment = next(
            held for held in index.segments if held.name == segment_name
        )
        if not 0 <= local < segment.doc_count():
            violations.append(
                Violation(
                    invariant="locations-resolve",
                    detail=(
                        f"id {external} points at {segment_name}:"
                        f"{local}, outside {segment.doc_count()}"
                    ),
                )
            )

    checks += 1
    for segment in index.segments:
        for doc in segment.tombstones:
            if not 0 <= doc < segment.doc_count():
                violations.append(
                    Violation(
                        invariant="tombstones-name-the-dead",
                        detail=(
                            f"{segment.name} holds a tombstone for "
                            f"document {doc} of {segment.doc_count()}"
                        ),
                    )
                )

    checks += 1
    if index.locations:
        top = max(index.locations)
        if top >= index.next_id:
            violations.append(
                Violation(
                    invariant="id-counter-ahead",
                    detail=(
                        f"id {top} exists but next_id is "
                        f"{index.next_id}; the counter will reissue"
                    ),
                )
            )

    checks += 1
    for segment in index.segments:
        for (field_name, term), postings in segment.postings.items():
            for posting in postings.rows:
                if posting.doc >= segment.doc_count():
                    violations.append(
                        Violation(
                            invariant="postings-inside-segment",
                            detail=(
                                f"{segment.name} {field_name}:{term} "
                                f"posts doc {posting.doc} of "
                                f"{segment.doc_count()}"
                            ),
                        )
                    )

    audit_index.checks_run = checks
    return violations


def audit_report(index: Index) -> str:
    violations = audit_index(index)
    checks = audit_index.checks_run
    if not violations:
        return (
            f"{checks} invariants verified, 0 violations; the index "
            f"keeps its promises"
        )
    lines = [f"{len(violations)} violation(s) across {checks} checks:"]
    for violation in violations:
        lines.append(f"  [{violation.invariant}] {violation.detail}")
    return "\n".join(lines)
