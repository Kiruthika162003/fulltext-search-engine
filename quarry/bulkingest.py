"""Bulk ingest: a thousand documents, each judged alone, all reported.

Bulk endpoints fail two classic ways: all-or-nothing, where one
bad document sinks nine hundred good ones, and silent-partial,
where the response says accepted and means mostly. The ingest
here does neither: each document is validated and admitted
independently, the response pairs every input position with its
outcome so the caller can retry exactly the failures, and the
summary states admitted, refused, and duplicated counts that
sum to the batch size, arithmetic the client can assert on.
Idempotency is per document via caller-supplied keys: a key
seen before is reported as a duplicate of its original
position, not re-indexed and not an error, because retried
batches are the normal case in bulk traffic, and punishing
retries teaches clients not to retry, which loses data the
other way around. An empty batch is refused; there is no
useful meaning for a bulk call that bulks nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass(frozen=True)
class RowOutcome:
    position: int
    status: str
    detail: str

    def line(self) -> str:
        return f"[{self.position}] {self.status}: {self.detail}"


@dataclass
class BulkIngest:
    validator: object
    seen_keys: dict[str, int] = field(default_factory=dict)
    admitted_documents: list[dict[str, object]] = field(
        default_factory=list
    )

    def ingest(
        self,
        batch: list[tuple[str, dict[str, object]]],
    ) -> tuple[list[RowOutcome], str]:
        if not batch:
            raise Invalid(
                "an empty batch bulks nothing; do not call for it"
            )
        outcomes = []
        admitted = refused = duplicated = 0
        for position, (key, document) in enumerate(batch):
            if not key.strip():
                refused += 1
                outcomes.append(
                    RowOutcome(
                        position=position,
                        status="refused",
                        detail=(
                            "an empty idempotency key cannot "
                            "deduplicate anything"
                        ),
                    )
                )
                continue
            if key in self.seen_keys:
                duplicated += 1
                outcomes.append(
                    RowOutcome(
                        position=position,
                        status="duplicate",
                        detail=(
                            f"key {key!r} first admitted at "
                            f"position {self.seen_keys[key]}; not "
                            f"re-indexed, not an error"
                        ),
                    )
                )
                continue
            problem = self._validate(document)
            if problem is not None:
                refused += 1
                outcomes.append(
                    RowOutcome(
                        position=position,
                        status="refused",
                        detail=problem,
                    )
                )
                continue
            self.seen_keys[key] = position
            self.admitted_documents.append(document)
            admitted += 1
            outcomes.append(
                RowOutcome(
                    position=position,
                    status="admitted",
                    detail=f"key {key!r}",
                )
            )
        total = admitted + refused + duplicated
        summary = (
            f"{admitted} admitted, {refused} refused, "
            f"{duplicated} duplicate(s) = {total} of {len(batch)}"
        )
        return outcomes, summary

    def _validate(self, document: dict[str, object]) -> str | None:
        if not document:
            return "an empty document indexes nothing"
        checker = getattr(self.validator, "check", None)
        if checker is None:
            return None
        return checker(document)

    def retry_positions(
        self, outcomes: list[RowOutcome]
    ) -> list[int]:
        return [
            held.position
            for held in outcomes
            if held.status == "refused"
        ]
