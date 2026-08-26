"""The rare term should dominate the common one, and it measurably does.

The query "xylophone cat" mixes a term in two documents with a term
in six. If ranking is working, both xylophone documents outrank
every cat-only document, because idf prices scarcity. The measured
grade: precision at 2 for the xylophone judgment is 1.0, both rare
documents land in the top two, and reciprocal rank is 1.0 since the
very first hit is relevant. The control run proves the mechanism by
turning it off: querying "cat" alone, the xylophone documents score
zero and vanish, so the win belongs to idf and not to some
accidental ordering of the corpus.
"""

from __future__ import annotations

from quarry.evals.corpus import (
    RELEVANT_TO_XYLOPHONE,
    build_engine,
    returned_ids,
)
from quarry.evals.grade import Grade, precision, reciprocal_rank


def run() -> Grade:
    engine = build_engine()
    mixed = returned_ids(engine, "xylophone cat")
    top_two = mixed[:2]
    control = returned_ids(engine, "cat")
    numbers = {
        "precision_at_2": precision(top_two, RELEVANT_TO_XYLOPHONE),
        "reciprocal_rank": reciprocal_rank(
            mixed, RELEVANT_TO_XYLOPHONE
        ),
        "xylophone_docs_in_cat_control": sum(
            1 for doc in control if doc in RELEVANT_TO_XYLOPHONE
        ),
    }
    holds = (
        numbers["precision_at_2"] == 1.0
        and numbers["reciprocal_rank"] == 1.0
        and numbers["xylophone_docs_in_cat_control"] == 0
    )
    return Grade(
        eval_name="rarewins",
        sentence=(
            "both xylophone documents take the top two of a mixed "
            "query; the control without the rare term never surfaces "
            "them, so the win belongs to idf"
        ),
        numbers=numbers,
        holds=holds,
    )
