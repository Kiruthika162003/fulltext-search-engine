"""Retention policy: documents age out by rule, never by surprise.

Keeping everything forever is a lawsuit and deleting by hand is
a different one, so retention is a declared policy: each class
of document carries a keep period in days, the sweep computes
what expired against a clock the caller provides, and nothing
leaves the index without appearing in the sweep report first,
because a retention system's deletions must be auditable back
to the rule that caused them. Two protections are structural: a
document under legal hold survives every sweep no matter how
expired, holds being the one rule that outranks the calendar,
and a sweep that would remove more than the guard share of the
corpus aborts and asks for a human, since a policy typo that
expires everything should die in the dry run, not in the index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

GUARD_SHARE = 0.5


@dataclass(frozen=True)
class RetentionRule:
    doc_class: str
    keep_days: int

    def __post_init__(self) -> None:
        if self.keep_days <= 0:
            raise Invalid(
                f"{self.doc_class}: keeping for {self.keep_days} "
                f"days means never indexing; refuse at the door "
                f"instead"
            )


@dataclass
class RetentionPolicy:
    rules: dict[str, RetentionRule] = field(default_factory=dict)
    holds: set[int] = field(default_factory=set)
    swept: list[str] = field(default_factory=list)

    def declare(self, rule: RetentionRule) -> None:
        self.rules[rule.doc_class] = rule

    def hold(self, external: int, reason: str) -> str:
        if not reason.strip():
            raise Invalid(
                "a legal hold without a reason will not survive "
                "the deposition"
            )
        self.holds.add(external)
        return f"doc {external} held: {reason}"

    def release_hold(self, external: int) -> None:
        if external not in self.holds:
            raise Missing(
                f"doc {external} is not under hold; releasing "
                f"nothing usually means the wrong id"
            )
        self.holds.discard(external)

    def expired(
        self,
        documents: list[tuple[int, str, int]],
        today_epoch_day: int,
    ) -> list[tuple[int, str]]:
        """(external, class, indexed_day) -> [(external, why)]."""
        out = []
        for external, doc_class, indexed_day in documents:
            rule = self.rules.get(doc_class)
            if rule is None:
                raise Missing(
                    f"doc {external} has class {doc_class!r} and no "
                    f"rule covers it; unclassified documents do not "
                    f"silently live forever"
                )
            age = today_epoch_day - indexed_day
            if age < 0:
                raise Invalid(
                    f"doc {external} was indexed {-age} day(s) in "
                    f"the future; the clock or the record is wrong"
                )
            if age <= rule.keep_days:
                continue
            if external in self.holds:
                continue
            out.append(
                (
                    external,
                    f"{doc_class} kept {rule.keep_days}d, "
                    f"aged {age}d",
                )
            )
        return out

    def sweep(
        self,
        documents: list[tuple[int, str, int]],
        today_epoch_day: int,
    ) -> tuple[list[int], str]:
        if not documents:
            raise Invalid("sweeping an empty corpus sweeps nothing")
        doomed = self.expired(documents, today_epoch_day)
        share = len(doomed) / len(documents)
        if share > GUARD_SHARE:
            raise Invalid(
                f"this sweep would remove {share:.0%} of the corpus, "
                f"over the {GUARD_SHARE:.0%} guard; a policy typo "
                f"should die in the dry run, not in the index"
            )
        held_count = sum(
            1
            for external, doc_class, indexed_day in documents
            if external in self.holds
        )
        for external, why in doomed:
            self.swept.append(f"doc {external}: {why}")
        report = (
            f"swept {len(doomed)} of {len(documents)}; "
            f"{held_count} under hold survived regardless"
        )
        return [external for external, _ in doomed], report

    def ledger(self) -> str:
        if not self.swept:
            return "nothing swept yet"
        return "\n".join(self.swept)
