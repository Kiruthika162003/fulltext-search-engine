"""Query rate limiting: the box is finite and the refusal is polite.

An open search endpoint meets scrapers, runaway retry loops, and
the analyst whose notebook fires four hundred queries a second,
and the engine's job is to survive all three without punishing the
users behind them. Each caller gets a token bucket, full burst at
rest, refilled by the clock, so a human's bursty afternoon fits
inside the burst while a sustained flood drains dry. The refusal
carries the retry-after computed from the refill rate, because a
caller told when to come back comes back then, and a caller told
no comes back immediately and angrier. The last stand is global:
a total ceiling across all callers that sheds the heaviest bucket
holders first when the box itself is at risk, heaviest first
because shedding the light users to save room for the flood is
the exact wrong sacrifice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass
class Bucket:
    rate: float
    burst: int
    level: float = 0.0
    refilled_at: int = 0
    spent: int = 0

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.burst <= 0:
            raise Invalid("a bucket needs a rate and a burst")
        self.level = float(self.burst)

    def refill(self, now: int) -> None:
        elapsed = now - self.refilled_at
        if elapsed > 0:
            self.level = min(
                float(self.burst), self.level + elapsed * self.rate
            )
            self.refilled_at = now

    def take(self, now: int) -> bool:
        self.refill(now)
        if self.level >= 1.0:
            self.level -= 1.0
            self.spent += 1
            return True
        return False

    def retry_after(self, now: int) -> int:
        self.refill(now)
        if self.level >= 1.0:
            return 0
        needed = 1.0 - self.level
        ticks = needed / self.rate
        whole = int(ticks)
        return whole if ticks == whole else whole + 1


@dataclass(frozen=True)
class Admission:
    allowed: bool
    retry_after: int
    reason: str


@dataclass
class QueryGate:
    rate: float = 1.0
    burst: int = 10
    global_ceiling: int = 1000
    buckets: dict[str, Bucket] = field(default_factory=dict)
    admitted_total: int = 0
    shed: int = 0

    def __post_init__(self) -> None:
        if self.global_ceiling <= 0:
            raise Invalid("a global ceiling of zero serves nobody")

    def _bucket(self, caller: str) -> Bucket:
        if caller not in self.buckets:
            self.buckets[caller] = Bucket(
                rate=self.rate, burst=self.burst
            )
        return self.buckets[caller]

    def admit(self, caller: str, now: int) -> Admission:
        if not caller:
            raise Invalid("an anonymous caller cannot hold a bucket")
        if self.admitted_total >= self.global_ceiling:
            heaviest = max(
                self.buckets.values(), key=lambda held: held.spent
            )
            if self._bucket(caller) is heaviest:
                self.shed += 1
                return Admission(
                    allowed=False,
                    retry_after=heaviest.retry_after(now),
                    reason=(
                        "the box is at its ceiling and this caller is "
                        "its heaviest user; shed heaviest-first "
                        "because sacrificing the light users to save "
                        "room for the flood is backwards"
                    ),
                )
        bucket = self._bucket(caller)
        if bucket.take(now):
            self.admitted_total += 1
            return Admission(
                allowed=True, retry_after=0, reason="inside the burst"
            )
        wait = bucket.retry_after(now)
        return Admission(
            allowed=False,
            retry_after=wait,
            reason=f"bucket dry; retry in {wait}",
        )

    def new_window(self) -> None:
        self.admitted_total = 0

    def pressure(self) -> str:
        heaviest = (
            max(self.buckets.items(), key=lambda row: row[1].spent)
            if self.buckets
            else None
        )
        head = (
            f"{self.admitted_total}/{self.global_ceiling} admitted "
            f"this window, {self.shed} shed"
        )
        if heaviest is None:
            return head
        name, bucket = heaviest
        return f"{head}; heaviest caller {name} at {bucket.spent} queries"
