"""Retry scheduling: backoff that spreads, caps, and gives up.

Retries against a struggling dependency either heal the blip
or finish the job of taking it down, and the difference is
three disciplines. Exponential backoff doubles the wait per
attempt so a real outage sees retry pressure fall instead of
compound. Deterministic jitter spreads callers apart, a hash
of the caller's name shifting each schedule within its window,
because a thousand clients backing off in lockstep arrive back
in lockstep, the thundering herd wearing a safety feature. And
the budget ends it: attempts are finite and the final state is
a named give-up carrying the schedule it tried, because a
retry loop without an end is an outage generator with
patience. The schedule is computed up front and printable
before anything runs, so a reviewer can read exactly how a
client will behave on the worst day instead of deriving it
from arithmetic in a hot loop.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid

BASE_WAIT = 100
MAX_WAIT = 8000
MAX_ATTEMPTS = 6


def _jitter_share(caller: str, attempt: int) -> float:
    digest = hashlib.sha256(
        f"{caller}|{attempt}".encode()
    ).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


@dataclass(frozen=True)
class RetryPlan:
    caller: str
    waits_ms: tuple[int, ...]

    def total_wait(self) -> int:
        return sum(self.waits_ms)

    def page(self) -> str:
        lines = [f"retry plan for {self.caller}:"]
        for attempt, wait in enumerate(self.waits_ms, start=1):
            lines.append(f"  attempt {attempt}: wait {wait}ms")
        lines.append(
            f"then GIVE UP after {len(self.waits_ms)} attempt(s) "
            f"and {self.total_wait()}ms of patience"
        )
        return "\n".join(lines)


def plan(
    caller: str, attempts: int = MAX_ATTEMPTS
) -> RetryPlan:
    if not caller.strip():
        raise Invalid(
            "a nameless caller cannot be jittered apart from the "
            "herd"
        )
    if not 1 <= attempts <= MAX_ATTEMPTS:
        raise Invalid(
            f"{attempts} attempt(s) is outside [1, {MAX_ATTEMPTS}]; "
            f"a retry loop without an end is an outage generator "
            f"with patience"
        )
    waits = []
    for attempt in range(attempts):
        ceiling = min(BASE_WAIT * (2**attempt), MAX_WAIT)
        floor = ceiling // 2
        share = _jitter_share(caller, attempt)
        waits.append(floor + int(share * (ceiling - floor)))
    return RetryPlan(caller=caller, waits_ms=tuple(waits))


def herd_spread(callers: list[str], attempt: int) -> str:
    if len(callers) < 2:
        raise Invalid("a herd of one cannot thunder")
    waits = sorted(
        plan(caller).waits_ms[attempt] for caller in callers
    )
    distinct = len(set(waits))
    span = waits[-1] - waits[0]
    return (
        f"attempt {attempt}: {len(callers)} callers spread over "
        f"{span}ms with {distinct} distinct wait(s); lockstep "
        f"would be 1"
    )
