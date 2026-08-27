"""Field masking: what a role must not see is removed, not hidden.

Document-level permissions decide whether you may find a
record; field masking decides what the record shows you once
found: support sees the order but not the card fingerprint,
analytics sees everything but the buyer's name. Masks are
declared per role as the fields REMOVED, not the fields kept,
because a keep-list silently exposes every field added after
the list was written, and the mask is applied by building a
new document rather than blanking values, since an empty
string where the salary was is itself a disclosure that a
salary exists. Unknown roles get the strictest standing mask
rather than none, masking composes by union when a caller
holds several roles is false, the INTERSECTION of visibility,
union of removals, because privileges do not add fields back,
and the audit answers who can see this field across every
role in one call, the question the privacy review always
asks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass
class MaskBook:
    removals: dict[str, frozenset[str]] = field(
        default_factory=dict
    )

    def declare(self, role: str, removed: set[str]) -> str:
        if not role.strip():
            raise Invalid("a nameless role cannot be granted")
        if role in self.removals:
            raise Invalid(
                f"{role} already has a mask; masks change by "
                f"declaring a new role book, not by editing in "
                f"place"
            )
        self.removals[role] = frozenset(removed)
        listed = ", ".join(sorted(removed)) or "nothing"
        return f"{role} loses: {listed}"

    def _strictest(self) -> frozenset[str]:
        if not self.removals:
            raise Invalid(
                "no masks declared; masking cannot default to "
                "showing everything"
            )
        return max(self.removals.values(), key=len)

    def mask_for(self, roles: list[str]) -> frozenset[str]:
        if not roles:
            return self._strictest()
        gathered: set[str] = set()
        for role in roles:
            held = self.removals.get(role)
            if held is None:
                gathered |= self._strictest()
            else:
                gathered |= held
        return frozenset(gathered)

    def apply(
        self, document: dict[str, object], roles: list[str]
    ) -> dict[str, object]:
        removed = self.mask_for(roles)
        return {
            key: value
            for key, value in document.items()
            if key not in removed
        }

    def who_sees(self, field_name: str) -> list[str]:
        if not self.removals:
            raise Invalid("no masks declared; nobody is defined")
        return sorted(
            role
            for role, removed in self.removals.items()
            if field_name not in removed
        )

    def audit_page(self, field_names: list[str]) -> str:
        lines = []
        for name in sorted(field_names):
            viewers = self.who_sees(name)
            shown = ", ".join(viewers) if viewers else "NOBODY"
            lines.append(f"{name}: visible to {shown}")
        return "\n".join(lines)
