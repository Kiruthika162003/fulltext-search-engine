"""The single-writer lock: leases expire, fences make stale writers safe.

One index, one writer, and the failure that matters is not two
writers starting, it is one writer pausing, being declared
dead, and waking up mid-write after its replacement started.
The lock is a lease: acquired with a duration, renewable
before expiry, and expiring on its own so a dead writer never
needs a human to unstick the lock. The fencing token is the
half that makes expiry safe: every acquisition mints a token
larger than every earlier one, downstream writes carry their
token, and the store refuses any write fenced below the
highest token it has seen, so the woken zombie's writes bounce
off the fence instead of corrupting the index. Renewals keep
the token, because the same writer continuing is the same
authority, and a renewal after expiry is refused as a new
acquisition in disguise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Stale


@dataclass
class WriterLease:
    holder: str = ""
    token: int = 0
    expires_at: int = 0

    def held_by(self, who: str, now: int) -> bool:
        return self.holder == who and now < self.expires_at


@dataclass
class WriteLock:
    lease: WriterLease = field(default_factory=WriterLease)
    highest_token: int = 0

    def acquire(
        self, who: str, now: int, duration: int
    ) -> int:
        if not who.strip():
            raise Invalid("a nameless writer cannot hold a lease")
        if duration <= 0:
            raise Invalid("a lease of no duration expires at birth")
        if (
            self.lease.holder
            and self.lease.holder != who
            and now < self.lease.expires_at
        ):
            raise Frozen(
                f"{self.lease.holder} holds the lease until "
                f"{self.lease.expires_at}; wait for expiry, do "
                f"not break the lock"
            )
        self.highest_token += 1
        self.lease = WriterLease(
            holder=who,
            token=self.highest_token,
            expires_at=now + duration,
        )
        return self.highest_token

    def renew(self, who: str, now: int, duration: int) -> str:
        if self.lease.holder != who:
            raise Invalid(
                f"{who} does not hold the lease; renewal is for "
                f"the holder"
            )
        if now >= self.lease.expires_at:
            raise Stale(
                f"the lease expired at {self.lease.expires_at}; "
                f"a renewal after expiry is a new acquisition in "
                f"disguise, acquire honestly"
            )
        self.lease.expires_at = now + duration
        return (
            f"{who} renewed until {self.lease.expires_at}, same "
            f"token {self.lease.token}"
        )


@dataclass
class FencedStore:
    highest_seen: int = 0
    writes: list[str] = field(default_factory=list)
    bounced: int = 0

    def write(self, payload: str, fence_token: int) -> str:
        if fence_token < self.highest_seen:
            self.bounced += 1
            raise Stale(
                f"fence {fence_token} is below the highest seen "
                f"({self.highest_seen}); a woken zombie bounces "
                f"off the fence instead of corrupting the index"
            )
        self.highest_seen = fence_token
        self.writes.append(f"[{fence_token}] {payload}")
        return f"written under fence {fence_token}"

    def ledger(self) -> str:
        return (
            f"{len(self.writes)} write(s), {self.bounced} "
            f"bounced, fence at {self.highest_seen}"
        )
