"""Bulk ingestion: the batch succeeds or fails per document, never whole.

A bulk request carrying five thousand documents where one has a
bad field must not throw away the other 4,999, and must not
pretend all five thousand landed either. Every document in the
batch gets its own verdict, accepted with its new id or rejected
with the exact refusal, positions preserved so the caller can zip
verdicts back onto inputs. The failure budget is the circuit
breaker for garbage feeds: past a declared share of rejects the
rest of the batch is refused unexamined with the reason, because
a feed sending ninety percent garbage has a broken producer, and
politely validating five thousand broken rows one by one is how
an ingestion pipeline spends its morning accomplishing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, QuarryError
from quarry.writer import Index

FAILURE_BUDGET = 0.5
MINIMUM_SAMPLE = 10


@dataclass(frozen=True)
class RowVerdict:
    position: int
    accepted: bool
    external: int | None
    refusal: str | None


@dataclass(frozen=True)
class BatchReceipt:
    verdicts: tuple[RowVerdict, ...]
    accepted: int
    rejected: int
    abandoned_after: int | None

    def failed_rows(self) -> list[RowVerdict]:
        return [held for held in self.verdicts if not held.accepted]


@dataclass
class BulkLoader:
    index: Index
    failure_budget: float = FAILURE_BUDGET
    batches: int = 0

    def __post_init__(self) -> None:
        if not 0.0 < self.failure_budget <= 1.0:
            raise Invalid("the failure budget is a fraction over zero")

    def load(self, documents: list[dict[str, object]]) -> BatchReceipt:
        if not documents:
            raise Invalid("an empty batch is a heartbeat, not an ingest")
        self.batches += 1
        verdicts: list[RowVerdict] = []
        accepted = 0
        rejected = 0
        abandoned_after: int | None = None
        for position, document in enumerate(documents):
            checked = max(position, 1)
            if (
                position >= MINIMUM_SAMPLE
                and rejected / checked > self.failure_budget
            ):
                abandoned_after = position
                refusal = (
                    f"batch abandoned: {rejected} rejects in "
                    f"{position} rows crossed the "
                    f"{self.failure_budget:.0%} budget; fix the "
                    f"producer"
                )
                for rest in range(position, len(documents)):
                    verdicts.append(
                        RowVerdict(
                            position=rest,
                            accepted=False,
                            external=None,
                            refusal=refusal,
                        )
                    )
                rejected += len(documents) - position
                break
            try:
                external = self.index.add(document)
                verdicts.append(
                    RowVerdict(
                        position=position,
                        accepted=True,
                        external=external,
                        refusal=None,
                    )
                )
                accepted += 1
            except QuarryError as refused:
                verdicts.append(
                    RowVerdict(
                        position=position,
                        accepted=False,
                        external=None,
                        refusal=str(refused),
                    )
                )
                rejected += 1
        self.index.flush()
        return BatchReceipt(
            verdicts=tuple(verdicts),
            accepted=accepted,
            rejected=rejected,
            abandoned_after=abandoned_after,
        )
