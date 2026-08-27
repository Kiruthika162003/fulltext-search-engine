"""Optimistic updates: bring the version you read, or lose politely.

Two editors open the same product page; both save. Without version
checks the second save silently erases the first, and the eraser
never learns. Every document here carries a version that bumps on
every write, updates must present the version they read, and a
stale presentation loses with the current version in the refusal
so the loser can re-read, merge, and retry instead of guessing.
The politeness is the design: last-write-wins is what happens by
default everywhere, and it is a data-loss policy with good
manners, so the refusal message names what changed underneath
rather than just saying no. Deletes take a version too, because
deleting what somebody else just rewrote is the same silent
erasure pointed the other way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass
class VersionedDocument:
    fields: dict[str, object]
    version: int


@dataclass
class VersionedStore:
    documents: dict[int, VersionedDocument] = field(default_factory=dict)
    next_id: int = 0
    conflicts_refused: int = 0

    def create(self, fields: dict[str, object]) -> tuple[int, int]:
        external = self.next_id
        self.next_id += 1
        self.documents[external] = VersionedDocument(
            fields=dict(fields), version=1
        )
        return external, 1

    def read(self, external: int) -> tuple[dict[str, object], int]:
        held = self.documents.get(external)
        if held is None:
            raise Missing(f"no document {external}")
        return dict(held.fields), held.version

    def update(
        self,
        external: int,
        fields: dict[str, object],
        read_version: int,
    ) -> int:
        held = self.documents.get(external)
        if held is None:
            raise Missing(f"no document {external}")
        if read_version != held.version:
            self.conflicts_refused += 1
            raise Invalid(
                f"document {external} is at version {held.version}, "
                f"you read {read_version}; someone saved underneath "
                f"you. Re-read, merge, and retry, because overwriting "
                f"now would erase their work without telling anyone"
            )
        held.fields = dict(fields)
        held.version += 1
        return held.version

    def delete(self, external: int, read_version: int) -> None:
        held = self.documents.get(external)
        if held is None:
            raise Missing(f"no document {external}")
        if read_version != held.version:
            self.conflicts_refused += 1
            raise Invalid(
                f"document {external} moved to version {held.version} "
                f"since you read {read_version}; deleting what "
                f"somebody just rewrote is the same erasure pointed "
                f"the other way"
            )
        del self.documents[external]

    def merge_hint(
        self, external: int, yours: dict[str, object], read_version: int
    ) -> str:
        """What changed underneath: the merge's shopping list."""
        current, version = self.read(external)
        if version == read_version:
            return "nothing moved; retry the update as read"
        lines = [
            f"version {read_version} -> {version}; fields that moved:"
        ]
        for name in sorted(set(current) | set(yours)):
            theirs = current.get(name)
            mine = yours.get(name)
            if theirs != mine:
                lines.append(
                    f"  {name}: theirs {theirs!r}, yours {mine!r}"
                )
        return "\n".join(lines)
