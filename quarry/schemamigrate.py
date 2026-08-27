"""Schema migration: the plan is computed, judged, and only then run.

Schemas need to change and sealed schemas cannot, which is the
point of sealing: change arrives as a migration to a NEW schema
with the documents reindexed across, never as mutation in place.
The migrator diffs old against new and classifies every field
change by what it costs: adding a field is free, dropping one
loses data and must be acknowledged by name, changing a field's
kind is a rebuild of that field, and renames are only believed
when declared explicitly, because guessing that author became
writer from shape alone will one day guess wrong about price
and cost. The plan prints before anything runs, and the
migration refuses to start while any loss goes unacknowledged,
so the person who runs it has read the words this drops body.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.schema import Schema


@dataclass(frozen=True)
class Step:
    action: str
    field_name: str
    detail: str

    def line(self) -> str:
        return f"{self.action} {self.field_name}: {self.detail}"


@dataclass(frozen=True)
class MigrationPlan:
    steps: tuple[Step, ...]
    losses: tuple[str, ...]

    def free(self) -> bool:
        return not self.losses and all(
            step.action == "add" for step in self.steps
        )

    def describe(self) -> str:
        if not self.steps:
            return "schemas are identical; nothing to migrate"
        lines = [step.line() for step in self.steps]
        if self.losses:
            listed = ", ".join(self.losses)
            lines.append(f"DATA LOSS: this drops {listed}")
        return "\n".join(lines)


def plan_migration(
    old: Schema, new: Schema, renames: dict[str, str] | None = None
) -> MigrationPlan:
    renames = renames or {}
    for source, target in renames.items():
        if source not in old.fields:
            raise Invalid(
                f"rename source {source} is not in the old schema"
            )
        if target not in new.fields:
            raise Invalid(
                f"rename target {target} is not in the new schema"
            )
    steps: list[Step] = []
    losses: list[str] = []
    renamed_sources = set(renames)
    renamed_targets = set(renames.values())

    for name in sorted(old.fields):
        if name in renamed_sources:
            target = renames[name]
            old_kind = old.get(name).kind
            new_kind = new.get(target).kind
            if old_kind != new_kind:
                raise Invalid(
                    f"rename {name} -> {target} also changes kind "
                    f"{old_kind} -> {new_kind}; do that in two "
                    f"migrations so each is checkable"
                )
            steps.append(
                Step(
                    action="rename",
                    field_name=name,
                    detail=f"becomes {target}, declared not guessed",
                )
            )
        elif name not in new.fields:
            steps.append(
                Step(
                    action="drop",
                    field_name=name,
                    detail="its data does not survive",
                )
            )
            losses.append(name)
        elif old.get(name).kind != new.get(name).kind:
            steps.append(
                Step(
                    action="rebuild",
                    field_name=name,
                    detail=(
                        f"kind changes {old.get(name).kind} -> "
                        f"{new.get(name).kind}; every document "
                        f"reindexes this field"
                    ),
                )
            )

    for name in sorted(new.fields):
        if name not in old.fields and name not in renamed_targets:
            steps.append(
                Step(
                    action="add",
                    field_name=name,
                    detail=(
                        f"new {new.get(name).kind} field, empty "
                        f"until documents carry it"
                    ),
                )
            )
    return MigrationPlan(steps=tuple(steps), losses=tuple(losses))


def migrate_documents(
    plan: MigrationPlan,
    documents: list[dict[str, object]],
    renames: dict[str, str] | None = None,
    acknowledge_loss: bool = False,
) -> list[dict[str, object]]:
    if plan.losses and not acknowledge_loss:
        listed = ", ".join(plan.losses)
        raise Invalid(
            f"the plan drops {listed} and nobody acknowledged it; "
            f"read the plan, then pass acknowledge_loss=True"
        )
    renames = renames or {}
    dropped = {
        step.field_name
        for step in plan.steps
        if step.action == "drop"
    }
    out = []
    for document in documents:
        moved: dict[str, object] = {}
        for key, value in document.items():
            if key in dropped:
                continue
            moved[renames.get(key, key)] = value
        out.append(moved)
    return out
