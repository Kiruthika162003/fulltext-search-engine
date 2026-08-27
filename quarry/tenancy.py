"""Multi-tenancy: every tenant gets a whole engine, and a metered one.

Sharing one index across tenants means sharing statistics, and
shared statistics leak: tenant A's vocabulary shapes tenant B's
idf, and a rare term for one customer scores wrong because another
customer uses it constantly. So isolation here is structural, one
engine per tenant, and the tenancy layer adds what multi-tenant
operation actually needs: quotas on documents and queries enforced
at the door with the tenant named in the refusal, per-tenant usage
metering for the bill, and the noisy-neighbour report that ranks
tenants by their share of the day's queries, because when the
platform is slow the first question is always whose traffic, and
the report answers it before anyone starts guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.engine import Engine, Response
from quarry.errors import Invalid, Missing
from quarry.schema import Schema


@dataclass(frozen=True)
class TenantQuota:
    max_documents: int
    max_queries_per_day: int

    def __post_init__(self) -> None:
        if self.max_documents <= 0 or self.max_queries_per_day <= 0:
            raise Invalid("quotas of zero are a refusal wearing a plan")


@dataclass
class Tenant:
    name: str
    engine: Engine
    quota: TenantQuota
    documents_held: int = 0
    queries_today: int = 0


@dataclass
class TenancyLayer:
    schema: Schema
    tenants: dict[str, Tenant] = field(default_factory=dict)

    def onboard(self, name: str, quota: TenantQuota) -> Tenant:
        if name in self.tenants:
            raise Invalid(f"tenant {name} is already onboarded")
        tenant = Tenant(
            name=name, engine=Engine(schema=self.schema), quota=quota
        )
        self.tenants[name] = tenant
        return tenant

    def _tenant(self, name: str) -> Tenant:
        if name not in self.tenants:
            raise Missing(f"no tenant named {name}")
        return self.tenants[name]

    def add(self, tenant_name: str, document: dict[str, object]) -> int:
        tenant = self._tenant(tenant_name)
        if tenant.documents_held >= tenant.quota.max_documents:
            raise Invalid(
                f"{tenant_name} is at its document quota of "
                f"{tenant.quota.max_documents}; the refusal names the "
                f"tenant so support does not guess"
            )
        external = tenant.engine.add(document)
        tenant.documents_held += 1
        return external

    def search(self, tenant_name: str, text: str) -> Response:
        tenant = self._tenant(tenant_name)
        if tenant.queries_today >= tenant.quota.max_queries_per_day:
            raise Invalid(
                f"{tenant_name} exhausted its {tenant.quota.max_queries_per_day} "
                f"queries for the day"
            )
        tenant.queries_today += 1
        return tenant.engine.search(text)

    def commit(self, tenant_name: str) -> None:
        self._tenant(tenant_name).engine.commit()

    def new_day(self) -> None:
        for tenant in self.tenants.values():
            tenant.queries_today = 0

    def bill(self) -> str:
        lines = []
        for name in sorted(self.tenants):
            tenant = self.tenants[name]
            lines.append(
                f"{name}: {tenant.documents_held} documents held, "
                f"{tenant.queries_today} queries today"
            )
        return "\n".join(lines) if lines else "no tenants onboarded"

    def noisy_neighbours(self) -> list[tuple[str, float]]:
        """Tenants by their share of today's queries, noisiest first."""
        total = sum(
            tenant.queries_today for tenant in self.tenants.values()
        )
        if total == 0:
            raise Invalid("a quiet day has no noise to rank")
        rows = [
            (name, round(tenant.queries_today / total, 4))
            for name, tenant in self.tenants.items()
        ]
        rows.sort(key=lambda held: (-held[1], held[0]))
        return rows

    def isolation_proof(self, left: str, right: str) -> bool:
        """Two tenants share nothing: not engines, not vocabularies."""
        first = self._tenant(left)
        second = self._tenant(right)
        return (
            first.engine is not second.engine
            and first.engine.index is not second.engine.index
            and first.engine.vocabulary is not second.engine.vocabulary
        )
