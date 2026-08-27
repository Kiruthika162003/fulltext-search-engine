"""The field census: fill rates and cardinality, before they bite.

Schema declarations promise fields; the census reports what
documents actually carry. Fill rate per field, because a facet
on a field 12 percent of documents fill is a facet that hides
88 percent of the corpus and someone should read that number
before shipping the sidebar. Cardinality class, constant, low,
or unbounded, measured from distinct values against document
count, because sorting works on any of them but faceting on an
unbounded field renders a thousand one-count buckets nobody
can use. And type consistency, the share of values matching
the field's dominant type, because a numeric field that is 2
percent strings is a feed bug wearing a schema's clothes. The
census never samples silently: run on a slice, it says which
slice, since a census of the first thousand documents
describes the first feed, not the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

LOW_CARDINALITY = 20


@dataclass(frozen=True)
class FieldReport:
    field_name: str
    fill_rate: float
    distinct: int
    cardinality: str
    type_consistency: float

    def line(self) -> str:
        warnings = []
        if self.fill_rate < 0.5:
            warnings.append(
                f"a facet here hides {1 - self.fill_rate:.0%} of "
                f"the corpus"
            )
        if self.cardinality == "unbounded":
            warnings.append(
                "faceting renders one-count buckets nobody can use"
            )
        if self.type_consistency < 1.0:
            warnings.append(
                "mixed types: a feed bug wearing a schema's clothes"
            )
        tail = f" [{'; '.join(warnings)}]" if warnings else ""
        return (
            f"{self.field_name}: {self.fill_rate:.0%} filled, "
            f"{self.distinct} distinct ({self.cardinality}), "
            f"types {self.type_consistency:.0%} consistent{tail}"
        )


def census_field(
    field_name: str, documents: list[dict[str, object]]
) -> FieldReport:
    if not documents:
        raise Invalid("a census over no documents counts nobody")
    values = [
        document[field_name]
        for document in documents
        if field_name in document and document[field_name] is not None
    ]
    fill_rate = round(len(values) / len(documents), 4)
    distinct = len({repr(value) for value in values})
    if distinct <= 1:
        cardinality = "constant"
    elif values and distinct > len(values) * 0.8:
        cardinality = "unbounded"
    elif distinct <= LOW_CARDINALITY:
        cardinality = "low"
    else:
        cardinality = "moderate"
    if values:
        type_counts: dict[str, int] = {}
        for value in values:
            name = type(value).__name__
            type_counts[name] = type_counts.get(name, 0) + 1
        dominant = max(type_counts.values())
        consistency = round(dominant / len(values), 4)
    else:
        consistency = 1.0
    return FieldReport(
        field_name=field_name,
        fill_rate=fill_rate,
        distinct=distinct,
        cardinality=cardinality,
        type_consistency=consistency,
    )


def census_page(
    documents: list[dict[str, object]],
    slice_note: str = "the whole corpus",
) -> str:
    if not documents:
        raise Invalid("a census over no documents counts nobody")
    field_names = sorted(
        {name for document in documents for name in document}
    )
    lines = [
        f"census over {len(documents)} document(s) ({slice_note}):"
    ]
    for name in field_names:
        lines.append(
            "  " + census_field(name, documents).line()
        )
    if slice_note != "the whole corpus":
        lines.append(
            f"SLICE: this describes {slice_note}, not the corpus"
        )
    return "\n".join(lines)
