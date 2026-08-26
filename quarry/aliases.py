"""Aliases: callers name an intention, operators move the target.

Application code should say "search the products index" and never
learn which physical index answered, because the day the mapping
changes is the day every hardcoded name becomes a migration ticket.
The alias table maps names to indexes with two invariants held at
write time: an alias always points at exactly one index, and swaps
are atomic, the old target replaced by the new in one operation
with no moment where the alias dangles. The swap records its
history, who moved it and from what to what, because the alias
table is the switchboard of every zero-downtime story and a
switchboard without a call log turns every incident into
archaeology.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.writer import Index


@dataclass(frozen=True)
class Swap:
    alias: str
    before: str | None
    after: str
    who: str
    reason: str


@dataclass
class AliasTable:
    indexes: dict[str, Index] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    history: list[Swap] = field(default_factory=list)

    def register(self, name: str, index: Index) -> None:
        if name in self.indexes:
            raise Invalid(f"index {name} is already registered")
        self.indexes[name] = index

    def point(
        self, alias: str, target: str, who: str, reason: str
    ) -> Swap:
        if target not in self.indexes:
            raise Missing(
                f"cannot point {alias} at {target}; no such index is "
                f"registered"
            )
        if not reason.strip():
            raise Invalid(
                "a swap without a reason turns the call log into noise"
            )
        before = self.aliases.get(alias)
        if before == target:
            raise Invalid(
                f"{alias} already points at {target}; a no-op swap "
                f"pollutes the history"
            )
        self.aliases[alias] = target
        swap = Swap(
            alias=alias,
            before=before,
            after=target,
            who=who,
            reason=reason,
        )
        self.history.append(swap)
        return swap

    def resolve(self, alias: str) -> Index:
        target = self.aliases.get(alias)
        if target is None:
            raise Missing(
                f"no alias named {alias}; registered aliases: "
                f"{', '.join(sorted(self.aliases)) or 'none'}"
            )
        return self.indexes[target]

    def target_of(self, alias: str) -> str:
        if alias not in self.aliases:
            raise Missing(f"no alias named {alias}")
        return self.aliases[alias]

    def aliases_of(self, index_name: str) -> list[str]:
        return sorted(
            alias
            for alias, target in self.aliases.items()
            if target == index_name
        )

    def unreferenced(self) -> list[str]:
        """Indexes no alias points at: retirement candidates, by name."""
        pointed = set(self.aliases.values())
        return sorted(
            name for name in self.indexes if name not in pointed
        )

    def call_log(self) -> str:
        if not self.history:
            return "no swaps yet"
        return "\n".join(
            f"{swap.alias}: {swap.before or '(new)'} -> {swap.after} "
            f"({swap.who}: {swap.reason})"
            for swap in self.history
        )
