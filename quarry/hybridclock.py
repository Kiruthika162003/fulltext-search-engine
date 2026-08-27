"""A hybrid logical clock: order survives the clocks that lie.

Replicated writes need an order everyone agrees on, wall clocks
across machines disagree by milliseconds that matter, and pure
logical counters lose the human question of when. The hybrid
stamp carries both: the physical time as observed, and a
logical counter that increments whenever the physical clock
fails to advance, so two writes in the same millisecond still
order, and a machine whose clock jumps backward keeps issuing
stamps that only move forward, absorbing the jump in the
counter instead of reordering history. Receiving a remote
stamp merges by taking the larger physical time and stepping
the counter past both sides, which is what makes the order
agree everywhere without a coordinator. The drift guard is the
operational half: a remote stamp too far ahead of local
physical time is refused rather than merged, because merging
it would drag this node's stamps into the future and every
node it later talks to inherits the lie.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, Stale

MAX_DRIFT = 1000


@dataclass(frozen=True)
class Stamp:
    physical: int
    logical: int

    def __post_init__(self) -> None:
        if self.physical < 0 or self.logical < 0:
            raise Invalid("stamps do not run before the epoch")

    def key(self) -> tuple[int, int]:
        return (self.physical, self.logical)

    def render(self) -> str:
        return f"{self.physical}.{self.logical}"


@dataclass
class HybridClock:
    node: str
    last: Stamp = Stamp(physical=0, logical=0)
    backward_jumps: int = 0

    def now(self, observed_physical: int) -> Stamp:
        if observed_physical < 0:
            raise Invalid("the wall clock ran before the epoch")
        if observed_physical > self.last.physical:
            fresh = Stamp(physical=observed_physical, logical=0)
        else:
            if observed_physical < self.last.physical:
                self.backward_jumps += 1
            fresh = Stamp(
                physical=self.last.physical,
                logical=self.last.logical + 1,
            )
        self.last = fresh
        return fresh

    def receive(
        self, remote: Stamp, observed_physical: int
    ) -> Stamp:
        if remote.physical > observed_physical + MAX_DRIFT:
            raise Stale(
                f"{self.node}: remote stamp {remote.render()} is "
                f"{remote.physical - observed_physical} ahead of "
                f"local time; merging it would drag this node "
                f"into the future and every peer inherits the lie"
            )
        physical = max(
            self.last.physical, remote.physical, observed_physical
        )
        if physical == self.last.physical == remote.physical:
            logical = max(self.last.logical, remote.logical) + 1
        elif physical == self.last.physical:
            logical = self.last.logical + 1
        elif physical == remote.physical:
            logical = remote.logical + 1
        else:
            logical = 0
        fresh = Stamp(physical=physical, logical=logical)
        self.last = fresh
        return fresh

    def health(self) -> str:
        note = (
            f"; absorbed {self.backward_jumps} backward jump(s)"
            if self.backward_jumps
            else ""
        )
        return f"{self.node} at {self.last.render()}{note}"


def happened_before(left: Stamp, right: Stamp) -> bool:
    return left.key() < right.key()
