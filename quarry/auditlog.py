"""The audit log: who changed what, hash-chained so edits show.

Search indexes hold documents someone will eventually dispute,
and the audit log is the record that survives the dispute: every
mutating operation appends an entry naming the actor, the verb,
the target, and a reason, and each entry carries the hash of the
one before it, so deleting or editing a line breaks every hash
after it and the tamper is arithmetic, not testimony. The log
refuses vague verbs because an entry that says changed something
audits nothing, and reading the log verifies the chain before
returning a single line, since an audit trail that skips its own
verification is a diary. Sequence numbers are dense by
construction; a gap is impossible to produce through the API and
finding one in storage means the storage was edited around it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid

VERBS = (
    "add",
    "delete",
    "reindex",
    "quota_raise",
    "curation",
    "schema_migrate",
)

SEED = "quarry-audit-v1"


def _entry_hash(
    sequence: int, previous: str, actor: str, verb: str,
    target: str, reason: str,
) -> str:
    body = "|".join(
        (str(sequence), previous, actor, verb, target, reason)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Entry:
    sequence: int
    actor: str
    verb: str
    target: str
    reason: str
    previous: str
    digest: str

    def line(self) -> str:
        return (
            f"#{self.sequence} {self.actor} {self.verb} "
            f"{self.target}: {self.reason} [{self.digest}]"
        )


@dataclass
class AuditLog:
    entries: list[Entry] = field(default_factory=list)

    def record(
        self, actor: str, verb: str, target: str, reason: str
    ) -> Entry:
        if verb not in VERBS:
            listed = ", ".join(VERBS)
            raise Invalid(
                f"verb {verb!r} audits nothing; the auditable verbs "
                f"are {listed}"
            )
        if not actor.strip() or not reason.strip():
            raise Invalid(
                "an audit entry without an actor and a reason is a "
                "diary entry; both are required"
            )
        sequence = len(self.entries)
        previous = (
            self.entries[-1].digest if self.entries else SEED
        )
        digest = _entry_hash(
            sequence, previous, actor, verb, target, reason
        )
        entry = Entry(
            sequence=sequence,
            actor=actor,
            verb=verb,
            target=target,
            reason=reason,
            previous=previous,
            digest=digest,
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> str:
        expected_previous = SEED
        for entry in self.entries:
            if entry.previous != expected_previous:
                return (
                    f"BROKEN at #{entry.sequence}: expected previous "
                    f"{expected_previous}, found {entry.previous}; "
                    f"the chain was edited"
                )
            recomputed = _entry_hash(
                entry.sequence,
                entry.previous,
                entry.actor,
                entry.verb,
                entry.target,
                entry.reason,
            )
            if recomputed != entry.digest:
                return (
                    f"BROKEN at #{entry.sequence}: the entry does "
                    f"not hash to its own digest; its content was "
                    f"edited"
                )
            expected_previous = entry.digest
        return f"chain intact: {len(self.entries)} entries"

    def read(
        self, actor: str | None = None, verb: str | None = None
    ) -> list[str]:
        verdict = self.verify()
        if verdict.startswith("BROKEN"):
            raise Invalid(verdict)
        return [
            entry.line()
            for entry in self.entries
            if (actor is None or entry.actor == actor)
            and (verb is None or entry.verb == verb)
        ]
