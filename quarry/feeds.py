"""Feed adaptation: other people's field names, mapped and accounted for.

Documents arrive shaped by whoever exported them, and the adapter
is where their names become the schema's names: a mapping declares
source field to index field, transformations are limited to the
three honest ones, rename, join, and constant, and anything the
mapping does not mention is dropped with a count rather than
smuggled through. Rows the mapping cannot save go to the dead
letter queue with the original row and the exact complaint
attached, because a dead letter without its body is a death
notice nobody can act on, and the queue is bounded with the
overflow counted since an unbounded dead letter queue is just
the data loss moved somewhere with a nicer name. The adapter
never invents required fields: a row missing one is dead on
arrival, not padded into a plausible lie.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

DEAD_LETTER_LIMIT = 100


@dataclass(frozen=True)
class FieldRule:
    target: str
    sources: tuple[str, ...]
    constant: str | None = None
    required: bool = False

    def __post_init__(self) -> None:
        if self.constant is not None and self.sources:
            raise Invalid(
                f"{self.target}: a constant with sources is two rules "
                f"wearing one name"
            )
        if self.constant is None and not self.sources:
            raise Invalid(
                f"{self.target}: no sources and no constant maps nothing"
            )


@dataclass(frozen=True)
class DeadLetter:
    row: dict
    complaint: str


@dataclass
class FeedAdapter:
    rules: list[FieldRule]
    dead_letter_limit: int = DEAD_LETTER_LIMIT
    dead_letters: list[DeadLetter] = field(default_factory=list)
    dead_letter_overflow: int = 0
    adapted: int = 0
    fields_dropped: int = 0

    def __post_init__(self) -> None:
        if not self.rules:
            raise Invalid("an adapter without rules adapts nothing")
        targets = [rule.target for rule in self.rules]
        if len(set(targets)) != len(targets):
            raise Invalid("two rules share a target; one field, one rule")
        if self.dead_letter_limit <= 0:
            raise Invalid("a dead letter queue needs room for its dead")

    def _bury(self, row: dict, complaint: str) -> None:
        if len(self.dead_letters) >= self.dead_letter_limit:
            self.dead_letter_overflow += 1
            return
        self.dead_letters.append(
            DeadLetter(row=dict(row), complaint=complaint)
        )

    def adapt(self, row: dict) -> dict[str, object] | None:
        shaped: dict[str, object] = {}
        for rule in self.rules:
            if rule.constant is not None:
                shaped[rule.target] = rule.constant
                continue
            present = [
                str(row[source])
                for source in rule.sources
                if source in row and row[source] not in (None, "")
            ]
            if not present:
                if rule.required:
                    self._bury(
                        row,
                        f"required field {rule.target} has no source "
                        f"among {', '.join(rule.sources)}",
                    )
                    return None
                continue
            shaped[rule.target] = " ".join(present)
        mapped_sources = {
            source for rule in self.rules for source in rule.sources
        }
        self.fields_dropped += sum(
            1 for key in row if key not in mapped_sources
        )
        self.adapted += 1
        return shaped

    def intake_report(self) -> str:
        buried = len(self.dead_letters) + self.dead_letter_overflow
        return (
            f"{self.adapted} rows adapted, {buried} dead "
            f"({self.dead_letter_overflow} past the queue), "
            f"{self.fields_dropped} unmapped fields dropped"
        )

    def first_complaints(self, limit: int = 3) -> list[str]:
        if limit <= 0:
            raise Invalid("a complaint list with no rows tells nothing")
        return [
            letter.complaint for letter in self.dead_letters[:limit]
        ]
