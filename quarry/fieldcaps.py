"""Field capabilities: what each field can do, answered before trying.

Clients discover a schema's abilities by trying operations and
reading errors unless the engine can simply say: this field
matches text, that one filters exactly, this one ranges and
sorts, that one is stored freight that answers nothing. The
capability matrix derives entirely from the field kind, text
fields search and highlight but refuse sorting because scores
order them, keywords filter and facet and sort, numerics
range and sort and bucket, stored fields do none of it, and
the matrix is queryable per field, per capability, and as one
page. Asking about an undeclared field lists what is declared,
and asking whether a capability exists anywhere returns the
fields that have it, which is the question a query builder UI
actually asks when deciding which dropdowns to draw.
"""

from __future__ import annotations

from quarry.errors import Missing
from quarry.schema import Schema

CAPABILITIES = (
    "match",
    "phrase",
    "highlight",
    "filter",
    "facet",
    "sort",
    "range",
)

BY_KIND = {
    "text": frozenset({"match", "phrase", "highlight"}),
    "keyword": frozenset({"filter", "facet", "sort"}),
    "numeric": frozenset({"filter", "sort", "range", "facet"}),
    "stored": frozenset(),
}

REFUSAL_REASONS = {
    ("text", "sort"): (
        "text fields order by score, not by value; sorting on "
        "prose alphabetizes sentences"
    ),
    ("text", "filter"): (
        "text is analyzed; exact filtering wants a keyword twin "
        "of this field"
    ),
    ("keyword", "match"): (
        "keywords match exactly or not at all; full-text matching "
        "wants a text twin"
    ),
    ("stored", "match"): (
        "stored fields are freight: kept, returned, never asked "
        "anything"
    ),
}


def capabilities_of(schema: Schema, field_name: str) -> frozenset[str]:
    declared = schema.get(field_name)
    return BY_KIND[declared.kind]


def can(
    schema: Schema, field_name: str, capability: str
) -> tuple[bool, str]:
    if capability not in CAPABILITIES:
        raise Missing(
            f"{capability!r} is not a capability; the vocabulary "
            f"is {', '.join(CAPABILITIES)}"
        )
    declared = schema.get(field_name)
    if capability in BY_KIND[declared.kind]:
        return True, f"{field_name} ({declared.kind}) can {capability}"
    reason = REFUSAL_REASONS.get(
        (declared.kind, capability),
        f"{declared.kind} fields do not {capability}",
    )
    return False, f"{field_name}: {reason}"


def fields_with(schema: Schema, capability: str) -> list[str]:
    if capability not in CAPABILITIES:
        raise Missing(
            f"{capability!r} is not a capability; the vocabulary "
            f"is {', '.join(CAPABILITIES)}"
        )
    return sorted(
        name
        for name in schema.fields
        if capability in BY_KIND[schema.get(name).kind]
    )


def capability_page(schema: Schema) -> str:
    lines = []
    for name in sorted(schema.fields):
        held = capabilities_of(schema, name)
        listed = (
            ", ".join(sorted(held)) if held else "stored freight"
        )
        lines.append(
            f"{name} ({schema.get(name).kind}): {listed}"
        )
    return "\n".join(lines)
