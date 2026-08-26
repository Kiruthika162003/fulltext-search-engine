"""Schema: fields declare how they are searched before anything is stored.

A field is a promise about future queries: text fields analyze and
rank, keyword fields match exactly and never stem, numeric fields
range and sort, and stored-only fields ride along for display
without costing a posting. The schema is sealed at index creation
because changing an analyzer under a live index silently splits the
corpus into two vocabularies that never meet, which is the classic
unfindable-document bug, and the seal converts it from a mystery
into a refusal. Every field records the analyzer identity it was
sealed with so a reopened index can prove it is being queried the
way it was written.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Missing
from quarry.tokenize import Analyzer

FIELD_KINDS = ("text", "keyword", "numeric", "stored")


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    analyzer: Analyzer | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise Invalid("a field needs a name")
        if self.kind not in FIELD_KINDS:
            raise Invalid(
                f"{self.name}: unknown kind {self.kind}; the choices "
                f"are {', '.join(FIELD_KINDS)}"
            )
        if self.kind == "text" and self.analyzer is None:
            raise Invalid(
                f"{self.name}: a text field needs its analyzer declared, "
                f"because the query side must use the same one"
            )
        if self.kind != "text" and self.analyzer is not None:
            raise Invalid(
                f"{self.name}: only text fields analyze; a {self.kind} "
                f"field with an analyzer is a category error"
            )

    def searchable(self) -> bool:
        return self.kind in ("text", "keyword", "numeric")


@dataclass
class Schema:
    fields: dict[str, Field] = field(default_factory=dict)
    sealed: bool = False

    def add_text(self, name: str, analyzer: Analyzer | None = None) -> None:
        self._add(Field(name=name, kind="text", analyzer=analyzer or Analyzer()))

    def add_keyword(self, name: str) -> None:
        self._add(Field(name=name, kind="keyword"))

    def add_numeric(self, name: str) -> None:
        self._add(Field(name=name, kind="numeric"))

    def add_stored(self, name: str) -> None:
        self._add(Field(name=name, kind="stored"))

    def _add(self, declared: Field) -> None:
        if self.sealed:
            raise Frozen(
                f"the schema is sealed; adding {declared.name} now would "
                f"split the corpus into two vocabularies"
            )
        if declared.name in self.fields:
            raise Invalid(f"{declared.name} is already declared")
        self.fields[declared.name] = declared

    def seal(self) -> None:
        if not self.fields:
            raise Invalid("sealing an empty schema indexes nothing")
        self.sealed = True

    def get(self, name: str) -> Field:
        if name not in self.fields:
            raise Missing(
                f"no field named {name}; declared: "
                f"{', '.join(sorted(self.fields))}"
            )
        return self.fields[name]

    def identity(self) -> str:
        rows = []
        for name in sorted(self.fields):
            held = self.fields[name]
            analyzer = (
                held.analyzer.identity() if held.analyzer else "none"
            )
            rows.append(f"{name}:{held.kind}:{analyzer}")
        return ";".join(rows)
