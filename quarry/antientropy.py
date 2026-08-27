"""Anti-entropy: replicas reconcile the whole corpus, cheaply.

Read repair heals what gets read; anti-entropy heals the rest.
Comparing every document across replicas is unaffordable, so
the corpus is bucketed by document id and each bucket carries a
digest folded from its members' ids and versions: agreeing
digests skip the bucket wholesale, and only disagreeing buckets
are opened for the document-level walk. The digest deliberately
covers versions rather than bodies, because two replicas
holding the same version of a document are in agreement by
definition of the replication protocol, and hashing bodies
would spend the savings the buckets exist to earn. The sync
report separates what was checked from what was actually
opened and repaired, and the direction of every repair is
newest wins by version, the same rule read repair uses, so the
two healers can never fight each other over an outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

BUCKET_COUNT = 16


def bucket_of(external: int) -> int:
    return external % BUCKET_COUNT


@dataclass
class VersionedStore:
    name: str
    versions: dict[int, int] = field(default_factory=dict)

    def put(self, external: int, version: int) -> None:
        standing = self.versions.get(external, 0)
        if version <= standing:
            raise Invalid(
                f"{self.name}: doc {external} v{version} does not "
                f"beat v{standing}; versions only move forward"
            )
        self.versions[external] = version

    def bucket_digest(self, bucket: int) -> int:
        folded = 0
        for external, version in self.versions.items():
            if bucket_of(external) == bucket:
                folded ^= hash((external, version)) & 0xFFFFFFFF
        return folded

    def bucket_members(self, bucket: int) -> dict[int, int]:
        return {
            external: version
            for external, version in self.versions.items()
            if bucket_of(external) == bucket
        }


@dataclass(frozen=True)
class SyncReport:
    buckets_checked: int
    buckets_opened: int
    repairs: tuple[str, ...]

    def line(self) -> str:
        return (
            f"checked {self.buckets_checked} bucket(s), opened "
            f"{self.buckets_opened}, applied {len(self.repairs)} "
            f"repair(s)"
        )


def synchronize(
    left: VersionedStore, right: VersionedStore
) -> SyncReport:
    if left.name == right.name:
        raise Invalid(
            "a store cannot anti-entropy against itself; that is "
            "a very slow no-op"
        )
    repairs: list[str] = []
    opened = 0
    for bucket in range(BUCKET_COUNT):
        if left.bucket_digest(bucket) == right.bucket_digest(bucket):
            continue
        opened += 1
        left_members = left.bucket_members(bucket)
        right_members = right.bucket_members(bucket)
        for external in sorted(
            set(left_members) | set(right_members)
        ):
            left_version = left_members.get(external, 0)
            right_version = right_members.get(external, 0)
            if left_version == right_version:
                continue
            if left_version > right_version:
                right.versions[external] = left_version
                repairs.append(
                    f"doc {external}: {right.name} v{right_version} "
                    f"-> v{left_version}"
                )
            else:
                left.versions[external] = right_version
                repairs.append(
                    f"doc {external}: {left.name} v{left_version} "
                    f"-> v{right_version}"
                )
    return SyncReport(
        buckets_checked=BUCKET_COUNT,
        buckets_opened=opened,
        repairs=tuple(repairs),
    )


def converged(
    left: VersionedStore, right: VersionedStore
) -> bool:
    return all(
        left.bucket_digest(bucket) == right.bucket_digest(bucket)
        for bucket in range(BUCKET_COUNT)
    )
