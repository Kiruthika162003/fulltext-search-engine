"""Collapsing buys diversity and the price is printed on the receipt.

A corpus where one newsletter owns four of the six matches: the
guess was a newsletter with guests, diversity 2 in the top four;
the measurement says the newsletter owns the entire top four,
diversity 1, a monoculture with no guests at all. Collapsed by source, the page shows
one row per source, diversity 3 of 3, and the receipt is what the
eval exists to pin: nothing was deleted, the folded issues are
countable under their representative, and the representative of
each group is exactly the group's best flat-ranking scorer, so
collapsing changed presentation and only presentation. A collapse
that quietly reorders inside groups or sheds documents is a
ranking bug wearing a UX feature, and this eval is where it gets
caught wearing it.
"""

from __future__ import annotations

from quarry.collapse import collapse_search
from quarry.evals.grade import Grade
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def _feedroom() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("source")
    schema.seal()
    index = Index(schema=schema)
    rows = [
        ("cat weekly issue one", "newsletter"),
        ("cat cat cat special edition", "newsletter"),
        ("cat weekly issue two", "newsletter"),
        ("cat weekly issue three", "newsletter"),
        ("lab report on cat cognition", "lab"),
        ("a reader letter about one cat", "letters"),
    ]
    for body, source in rows:
        index.add({"body": body, "source": source})
    index.flush()
    return index


def run() -> Grade:
    index = _feedroom()
    query = parse("cat")
    flat = search_index(index, query, limit=10).hits
    flat_top_sources = []
    for hit in flat[:4]:
        flat_top_sources.append(
            str(index.document(hit.external).get("source"))
        )
    flat_diversity = len(set(flat_top_sources))
    groups = collapse_search(index, query, by="source", limit=10)
    collapsed_diversity = len({group.key for group in groups})
    shown = {group.representative for group in groups}
    folded = {
        external for group in groups for external in group.folded
    }
    nothing_lost = shown | folded == {
        hit.external for hit in flat
    }
    best_by_source: dict[str, int] = {}
    for hit in flat:
        source = str(index.document(hit.external).get("source"))
        best_by_source.setdefault(source, hit.external)
    representatives_are_best = all(
        group.representative == best_by_source[str(group.key)]
        for group in groups
    )
    numbers = {
        "flat_diversity_top4": flat_diversity,
        "collapsed_diversity": collapsed_diversity,
        "nothing_lost": nothing_lost,
        "representatives_are_best": representatives_are_best,
    }
    holds = (
        flat_diversity == 1
        and collapsed_diversity == 3
        and nothing_lost
        and representatives_are_best
    )
    return Grade(
        eval_name="collapsefair",
        sentence=(
            "the flat top four is a one-source monoculture; collapsing "
            "lifts it to 3 of 3 while deleting nothing and keeping "
            "each group's best in front"
        ),
        numbers=numbers,
        holds=holds,
    )
