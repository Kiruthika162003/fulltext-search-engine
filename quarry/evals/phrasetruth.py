"""A phrase finds adjacency, not co-occurrence, and recall says which.

The corpus holds three documents where "black cat" appears as an
actual phrase and one, document 12, where black and cat both occur
without touching. The bare query returns the impostor along with
everything else, recall 1.0 with precision diluted; the quoted
query returns exactly the adjacent three, precision 1.0 at recall
1.0, and the impostor's exclusion is its own pinned number because
that one document is the entire difference between co-occurrence
and adjacency.
"""

from __future__ import annotations

from quarry.evals.corpus import (
    RELEVANT_TO_BLACK_CAT_PHRASE,
    build_engine,
    returned_ids,
)
from quarry.evals.grade import Grade, precision, recall


def run() -> Grade:
    engine = build_engine()
    bare = returned_ids(engine, "black cat", limit=20)
    quoted = returned_ids(engine, '"black cat"')
    numbers = {
        "bare_recall": recall(bare, RELEVANT_TO_BLACK_CAT_PHRASE),
        "bare_precision": precision(bare, RELEVANT_TO_BLACK_CAT_PHRASE),
        "quoted_precision": precision(
            quoted, RELEVANT_TO_BLACK_CAT_PHRASE
        ),
        "quoted_recall": recall(quoted, RELEVANT_TO_BLACK_CAT_PHRASE),
        "impostor_in_bare": 12 in bare,
        "impostor_in_quoted": 12 in quoted,
    }
    holds = (
        numbers["bare_recall"] == 1.0
        and numbers["quoted_precision"] == 1.0
        and numbers["quoted_recall"] == 1.0
        and numbers["impostor_in_bare"]
        and not numbers["impostor_in_quoted"]
    )
    return Grade(
        eval_name="phrasetruth",
        sentence=(
            "quoting keeps all three adjacent documents and sheds "
            "document 12, the co-occurrence impostor: precision 1.0 "
            "at recall 1.0"
        ),
        numbers=numbers,
        holds=holds,
    )
