"""Index lifecycle: retention is a policy, deletion is an appointment.

Data does not leave when people stop wanting it; it leaves when
something is scheduled to remove it, and this module is that
something. A lifecycle policy names phases with entry ages: fresh
indexes serve, aged ones close to writes, older ones lose their
replicas, and at the retention line they are deleted, each
transition journaled with the age that triggered it. Two rules
guard the sharp end. Deletion requires the policy to have been
declared with an explicit retention, because data that outlives
its purpose is liability, but data deleted by a default nobody
set is a lawsuit from the other direction. And holds outrank
policy: a legal hold on an index freezes every transition and says
so in the plan, because the day compliance calls is the day the
lifecycle engine must already know how to stand still.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

PHASES = ("serving", "read-only", "unreplicated", "deleted")


@dataclass(frozen=True)
class LifecyclePolicy:
    name: str
    read_only_after: int
    unreplicated_after: int
    delete_after: int

    def __post_init__(self) -> None:
        ladder = (
            self.read_only_after,
            self.unreplicated_after,
            self.delete_after,
        )
        if not all(age > 0 for age in ladder):
            raise Invalid(f"{self.name}: every phase needs a positive age")
        if list(ladder) != sorted(set(ladder)):
            raise Invalid(
                f"{self.name}: phases must strictly age forward; an "
                f"index cannot be deleted before it stops serving"
            )

    def phase_at(self, age: int) -> str:
        if age >= self.delete_after:
            return "deleted"
        if age >= self.unreplicated_after:
            return "unreplicated"
        if age >= self.read_only_after:
            return "read-only"
        return "serving"


@dataclass
class ManagedIndex:
    name: str
    born_at: int
    phase: str = "serving"
    held: bool = False
    hold_reason: str = ""


@dataclass
class LifecycleEngine:
    policy: LifecyclePolicy
    managed: dict[str, ManagedIndex] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def manage(self, name: str, born_at: int) -> None:
        if name in self.managed:
            raise Invalid(f"{name} is already managed")
        self.managed[name] = ManagedIndex(name=name, born_at=born_at)

    def hold(self, name: str, reason: str) -> None:
        if not reason.strip():
            raise Invalid(
                "a hold without a reason cannot be lifted responsibly"
            )
        row = self._get(name)
        row.held = True
        row.hold_reason = reason
        self.journal.append(f"{name}: HELD ({reason})")

    def release_hold(self, name: str, who: str) -> None:
        row = self._get(name)
        if not row.held:
            raise Invalid(f"{name} is not held; nothing to release")
        row.held = False
        self.journal.append(
            f"{name}: hold released by {who} (was: {row.hold_reason})"
        )
        row.hold_reason = ""

    def _get(self, name: str) -> ManagedIndex:
        if name not in self.managed:
            raise Missing(f"no managed index named {name}")
        return self.managed[name]

    def advance(self, now: int) -> list[str]:
        acted = []
        for row in sorted(self.managed.values(), key=lambda r: r.name):
            if row.held:
                continue
            age = now - row.born_at
            target = self.policy.phase_at(age)
            if target == row.phase:
                continue
            line = (
                f"{row.name}: {row.phase} -> {target} (age {age}, "
                f"policy {self.policy.name})"
            )
            row.phase = target
            self.journal.append(line)
            acted.append(line)
            if target == "deleted":
                self.deleted.append(row.name)
        for name in self.deleted:
            self.managed.pop(name, None)
        return acted

    def plan(self, now: int) -> str:
        lines = [f"policy {self.policy.name} at time {now}:"]
        for row in sorted(self.managed.values(), key=lambda r: r.name):
            age = now - row.born_at
            if row.held:
                lines.append(
                    f"  {row.name}: FROZEN by hold ({row.hold_reason}); "
                    f"policy would say {self.policy.phase_at(age)}"
                )
                continue
            target = self.policy.phase_at(age)
            state = (
                "stays"
                if target == row.phase
                else f"{row.phase} -> {target}"
            )
            lines.append(f"  {row.name}: age {age}, {state}")
        return "\n".join(lines)
