"""A day at the catalogue desk: search, facets, ranges, and a correction.

Run with: python -m examples.librarian
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.facets import facet, numeric_facet
from quarry.query import parse
from quarry.schema import Schema

BOOKS = [
    ("The Black Cat Mysteries", "fiction", 1998),
    ("Cats of the Ancient World", "history", 2004),
    ("A Practical Guide to Cat Care", "reference", 2015),
    ("The Cathedral Builders", "history", 2001),
    ("Feral Cats and City Life", "science", 2019),
    ("Dog Training Fundamentals", "reference", 2012),
    ("The Quiet Xylophone", "fiction", 2021),
]


def build_catalogue() -> Engine:
    schema = Schema()
    schema.add_text("title")
    schema.add_keyword("shelf")
    schema.add_numeric("year")
    schema.seal()
    engine = Engine(schema=schema)
    for title, shelf, year in BOOKS:
        engine.add({"title": title, "shelf": shelf, "year": year})
    engine.commit()
    return engine


def main() -> int:
    engine = build_catalogue()
    response = engine.search("title:cat", snippet_fields=("title",))
    print(f"query: {response.canonical}")
    for hit in response.hits:
        _, marked = hit.snippets[0]
        print(f"  [{hit.score:7.4f}] {marked}")
    shelves = facet(engine.index, parse("title:cat"), "shelf", top_n=3)
    print(shelves.line())
    decades = numeric_facet(
        engine.index,
        parse("title:cat"),
        "year",
        edges=(1990, 2000, 2010, 2020),
    )
    for row in decades:
        print(f"  {row.value}: {row.count}")
    correction = engine.search("title:catz")
    print(f"typo path: {correction.suggestion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
