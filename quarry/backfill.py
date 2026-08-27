"""Backfill orchestration: reindex millions, resumable and boring.

A backfill is a marathon of identical steps, and everything
that makes one dangerous is state: where it got to, what
failed, whether it can be resumed after the operator's laptop
dies. The orchestrator keeps that state explicit: work is
partitioned into numbered batches of declared size, each batch
moves from pending to done or parked, parked batches carry
their error and never block the ones behind them, and resume
picks up from the recorded frontier rather than from zero or
from memory. Two rates guard the run: a failure share past the
fuse aborts the whole backfill because a systematic error
should stop the marathon rather than park every batch one by
one, and the progress report always states batches, documents,
and the parked list, since a backfill reported as a bare
percentage hides exactly the failures the operator needs to
chase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Missing

FAILURE_FUSE = 0.25


@dataclass
class Backfill:
    total_documents: int
    batch_size: int
    done: set[int] = field(default_factory=set)
    parked: dict[int, str] = field(default_factory=dict)
    aborted: str = ""

    def __post_init__(self) -> None:
        if self.total_documents <= 0:
            raise Invalid("a backfill of nothing is already done")
        if self.batch_size <= 0:
            raise Invalid("batches need a positive size")

    def batch_count(self) -> int:
        return -(-self.total_documents // self.batch_size)

    def batch_bounds(self, batch: int) -> tuple[int, int]:
        if not 0 <= batch < self.batch_count():
            raise Missing(
                f"batch {batch} does not exist; batches run 0 to "
                f"{self.batch_count() - 1}"
            )
        start = batch * self.batch_size
        end = min(start + self.batch_size, self.total_documents)
        return start, end

    def frontier(self) -> int | None:
        for batch in range(self.batch_count()):
            if batch not in self.done and batch not in self.parked:
                return batch
        return None

    def _check_fuse(self) -> None:
        attempted = len(self.done) + len(self.parked)
        if attempted == 0:
            return
        share = len(self.parked) / attempted
        if share > FAILURE_FUSE and len(self.parked) >= 2:
            self.aborted = (
                f"{len(self.parked)} of {attempted} batches "
                f"failed ({share:.0%}); this is systematic, not "
                f"unlucky. Fix the cause, then resume"
            )

    def complete_batch(self, batch: int) -> str:
        if self.aborted:
            raise Frozen(f"backfill aborted: {self.aborted}")
        self.batch_bounds(batch)
        if batch in self.done:
            raise Invalid(
                f"batch {batch} is already done; doubling a batch "
                f"doubles its documents"
            )
        self.done.add(batch)
        self.parked.pop(batch, None)
        return f"batch {batch} done"

    def park_batch(self, batch: int, error: str) -> str:
        if self.aborted:
            raise Frozen(f"backfill aborted: {self.aborted}")
        self.batch_bounds(batch)
        if not error.strip():
            raise Invalid(
                "parking without the error loses the only clue"
            )
        self.parked[batch] = error
        self._check_fuse()
        if self.aborted:
            return f"batch {batch} parked; FUSE BLOWN: {self.aborted}"
        return f"batch {batch} parked; the marathon continues"

    def resume_point(self) -> str:
        if self.aborted:
            return f"aborted: {self.aborted}"
        held = self.frontier()
        if held is None:
            if self.parked:
                return (
                    f"frontier exhausted; {len(self.parked)} "
                    f"parked batch(es) remain to chase"
                )
            return "complete"
        start, end = self.batch_bounds(held)
        return f"resume at batch {held} (documents {start}-{end - 1})"

    def retry_parked(self, batch: int) -> str:
        if batch not in self.parked:
            raise Missing(f"batch {batch} is not parked")
        error = self.parked.pop(batch)
        self.aborted = ""
        return f"batch {batch} back in play (was: {error})"

    def progress(self) -> str:
        finished_docs = sum(
            self.batch_bounds(batch)[1] - self.batch_bounds(batch)[0]
            for batch in self.done
        )
        parked_list = (
            ", ".join(
                f"{batch}: {error}"
                for batch, error in sorted(self.parked.items())
            )
            or "none"
        )
        return (
            f"{len(self.done)}/{self.batch_count()} batches, "
            f"{finished_docs}/{self.total_documents} documents, "
            f"parked: {parked_list}"
        )
