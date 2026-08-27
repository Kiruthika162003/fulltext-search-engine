"""Saved searches: the query is a template, the holes are typed.

Dashboards and alerts reuse the same query shapes with different
values, and pasting values into query strings is an injection bug
waiting for its first quote mark. A template declares its holes
with types, term or number or keyword, and rendering fills them
with values that are escaped by construction: a term hole
analyzes like any typed word, a keyword hole passes exactly and
never grows operators, and a number hole refuses anything that
is not one. Missing and surplus parameters are both refused by
name, because a template silently rendering with a leftover hole
searches for the literal word placeholder and reports zero
results to someone's dashboard for a quarter. Saved templates
version on every edit so an alert firing strangely can say which
version of its query it was running.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

HOLE_TYPES = ("term", "keyword", "number")


@dataclass(frozen=True)
class Hole:
    name: str
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in HOLE_TYPES:
            raise Invalid(
                f"{self.name}: unknown hole type {self.kind}; the "
                f"choices are {', '.join(HOLE_TYPES)}"
            )

    def fill(self, value: object) -> str:
        if self.kind == "number":
            if not isinstance(value, int):
                raise Invalid(
                    f"{self.name} is a number hole and {value!r} is "
                    f"not one"
                )
            return str(value)
        text = str(value)
        if not text.strip():
            raise Invalid(f"{self.name}: an empty value fills nothing")
        for dangerous in ('"', ":", " OR ", "+", "-"):
            if dangerous in text and self.kind == "keyword":
                raise Invalid(
                    f"{self.name}: {text!r} carries query syntax; "
                    f"keyword holes pass values, never operators"
                )
        if self.kind == "term":
            return text.replace('"', "").strip()
        return text


@dataclass
class QueryTemplate:
    name: str
    shape: str
    holes: tuple[Hole, ...]
    version: int = 1

    def __post_init__(self) -> None:
        for hole in self.holes:
            marker = "{" + hole.name + "}"
            if marker not in self.shape:
                raise Invalid(
                    f"{self.name}: the shape never mentions "
                    f"{marker}; a hole with no home is a typo"
                )

    def render(self, **values: object) -> str:
        declared = {hole.name for hole in self.holes}
        provided = set(values)
        missing = declared - provided
        surplus = provided - declared
        if missing:
            raise Missing(
                f"{self.name}: no value for "
                f"{', '.join(sorted(missing))}"
            )
        if surplus:
            raise Invalid(
                f"{self.name}: surplus parameter(s) "
                f"{', '.join(sorted(surplus))}; a value with no hole "
                f"is a typo on the calling side"
            )
        rendered = self.shape
        for hole in self.holes:
            rendered = rendered.replace(
                "{" + hole.name + "}", hole.fill(values[hole.name])
            )
        return rendered


@dataclass
class TemplateBook:
    templates: dict[str, QueryTemplate] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)

    def save(self, template: QueryTemplate, who: str) -> None:
        existing = self.templates.get(template.name)
        if existing is not None:
            template = QueryTemplate(
                name=template.name,
                shape=template.shape,
                holes=template.holes,
                version=existing.version + 1,
            )
        self.templates[template.name] = template
        self.journal.append(
            f"{template.name} v{template.version} saved by {who}"
        )

    def render(self, name: str, **values: object) -> tuple[str, int]:
        template = self.templates.get(name)
        if template is None:
            raise Missing(f"no template named {name}")
        return template.render(**values), template.version
