"""Resource quotas per tenant: fair shares enforced before the work.

One tenant with a runaway indexing job can starve every other
tenant of a shared engine, so quotas meter the two resources
that actually run out, documents stored and searches per window,
and enforcement happens at admission rather than after the
damage. The window is a fixed-size ring of recent search costs
so a burst is judged against actual recent usage, not a
smoothed average that forgives it. Refusals name the quota, the
usage, and the shortfall, because a 429 with no arithmetic
teaches the caller nothing except resentment, and quota raises
are explicit declarations with an author, never automatic,
since an auto-raising quota is a quota only in the brochure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Missing


@dataclass(frozen=True)
class Quota:
    documents: int
    searches_per_window: int

    def __post_init__(self) -> None:
        if self.documents <= 0 or self.searches_per_window <= 0:
            raise Invalid(
                "a quota of zero is a ban wearing a quota's name; "
                "use a ban if that is meant"
            )


@dataclass
class TenantMeter:
    quota: Quota
    documents_held: int = 0
    window: list[int] = field(default_factory=list)

    def admit_document(self) -> None:
        if self.documents_held >= self.quota.documents:
            raise Frozen(
                f"document quota reached: {self.documents_held} of "
                f"{self.quota.documents} held; delete or ask for a "
                f"raise"
            )
        self.documents_held += 1

    def release_document(self) -> None:
        if self.documents_held == 0:
            raise Invalid(
                "releasing a document below zero means double "
                "counting somewhere"
            )
        self.documents_held -= 1

    def admit_search(self, tick: int) -> None:
        recent = [
            held
            for held in self.window
            if tick - held < self.quota.searches_per_window
        ]
        if len(recent) >= self.quota.searches_per_window:
            oldest = min(recent)
            wait = self.quota.searches_per_window - (tick - oldest)
            raise Frozen(
                f"search quota reached: "
                f"{len(recent)} searches inside the window of "
                f"{self.quota.searches_per_window}; room opens in "
                f"{wait} tick(s)"
            )
        recent.append(tick)
        self.window = recent

    def usage_line(self, name: str) -> str:
        return (
            f"{name}: {self.documents_held}/{self.quota.documents} "
            f"documents, {len(self.window)}/"
            f"{self.quota.searches_per_window} recent searches"
        )


@dataclass
class QuotaBoard:
    meters: dict[str, TenantMeter] = field(default_factory=dict)
    raises_granted: list[str] = field(default_factory=list)

    def enroll(self, tenant: str, quota: Quota) -> None:
        if tenant in self.meters:
            raise Invalid(
                f"{tenant} is already enrolled; raises go through "
                f"grant_raise so they are on the record"
            )
        self.meters[tenant] = TenantMeter(quota=quota)

    def meter(self, tenant: str) -> TenantMeter:
        held = self.meters.get(tenant)
        if held is None:
            raise Missing(f"no quota enrolled for {tenant}")
        return held

    def grant_raise(
        self, tenant: str, quota: Quota, author: str
    ) -> None:
        held = self.meter(tenant)
        if quota.documents < held.quota.documents:
            raise Invalid(
                f"{tenant}: shrinking a quota under held documents "
                f"strands data; evict first, then shrink"
            )
        held.quota = quota
        self.raises_granted.append(
            f"{tenant} raised to {quota.documents} documents, "
            f"{quota.searches_per_window}/window by {author}"
        )

    def board_report(self) -> str:
        if not self.meters:
            return "no tenants enrolled"
        lines = [
            held.usage_line(tenant)
            for tenant, held in sorted(self.meters.items())
        ]
        lines.extend(self.raises_granted)
        return "\n".join(lines)
