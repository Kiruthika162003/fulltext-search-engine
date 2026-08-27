"""Snapshot diffing: what changed between two index states, exactly.

Backups are only trusted when comparable: given two snapshots of
the same index taken at different times, the diff names the
documents added, removed, and changed, with changed decided by
content fingerprint rather than timestamp, because timestamps
lie whenever a reindex rewrites an unchanged document. The
fingerprint is a stable hash of the stored fields in sorted key
order so dict ordering cannot invent differences, the diff
refuses to compare snapshots of different schemas since an
added field makes every document look changed for the wrong
reason, and the summary states its arithmetic, adds plus
removes plus changes against the union size, so a restore
review can decide in one line whether the drift is routine or
a disaster wearing a routine's clothes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid


def fingerprint(document: dict[str, object]) -> str:
    body = "|".join(
        f"{key}={document[key]!r}" for key in sorted(document)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Snapshot:
    label: str
    schema_identity: str
    documents: dict[int, dict[str, object]]

    def fingerprints(self) -> dict[int, str]:
        return {
            external: fingerprint(held)
            for external, held in self.documents.items()
        }


@dataclass(frozen=True)
class SnapshotDiff:
    added: tuple[int, ...]
    removed: tuple[int, ...]
    changed: tuple[int, ...]
    unchanged: int

    def total_drift(self) -> int:
        return (
            len(self.added) + len(self.removed) + len(self.changed)
        )

    def summary(self) -> str:
        population = self.total_drift() + self.unchanged
        if self.total_drift() == 0:
            return f"identical: {self.unchanged} documents match"
        share = self.total_drift() / population
        return (
            f"{len(self.added)} added, {len(self.removed)} removed, "
            f"{len(self.changed)} changed of {population} "
            f"({share:.0%} drift)"
        )


def diff_snapshots(old: Snapshot, new: Snapshot) -> SnapshotDiff:
    if old.schema_identity != new.schema_identity:
        raise Invalid(
            f"snapshots disagree on schema ({old.schema_identity} "
            f"vs {new.schema_identity}); an added field makes every "
            f"document look changed for the wrong reason. Migrate, "
            f"snapshot, then compare"
        )
    if old.label == new.label:
        raise Invalid(
            f"both snapshots are labeled {old.label!r}; comparing a "
            f"snapshot to itself measures the diff tool, not the "
            f"index"
        )
    old_prints = old.fingerprints()
    new_prints = new.fingerprints()
    added = tuple(
        sorted(set(new_prints) - set(old_prints))
    )
    removed = tuple(
        sorted(set(old_prints) - set(new_prints))
    )
    shared = set(old_prints) & set(new_prints)
    changed = tuple(
        sorted(
            external
            for external in shared
            if old_prints[external] != new_prints[external]
        )
    )
    return SnapshotDiff(
        added=added,
        removed=removed,
        changed=changed,
        unchanged=len(shared) - len(changed),
    )


def changed_fields(
    old: Snapshot, new: Snapshot, external: int
) -> list[str]:
    if external not in old.documents or external not in new.documents:
        raise Invalid(
            f"doc {external} is not in both snapshots; field-level "
            f"diffs need both sides"
        )
    before = old.documents[external]
    after = new.documents[external]
    out = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            out.append(
                f"{key}: {before.get(key)!r} -> {after.get(key)!r}"
            )
    return out
