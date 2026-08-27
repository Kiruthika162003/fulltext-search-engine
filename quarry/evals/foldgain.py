"""Folding buys the beret documents, measured, both sides or neither.

Half the espresso corpus writes café with the accent and half
writes cafe without, and a searcher on an accentless keyboard
types cafe. Against the unfolded engine that query reaches only
its own spelling, recall 0.5. Fold both sides, documents at add
time and the query before search, and recall reaches 1.0 with
precision intact because folding marks does not invent matches.
The third measurement is the trap this eval exists to pin: fold
the index but not the query and the accented query finds nothing
at all, zero, worse than never folding, which is the
unfindable-document bug wearing a beret, and the number proves
the one-pipeline rule is load-bearing rather than stylistic.
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.evals.grade import Grade, precision, recall
from quarry.schema import Schema
from quarry.unicodefold import fold

ESPRESSO = {0, 1, 2, 3}

DOCUMENTS = (
    "the café on the corner pulls a fine shot",
    "a quiet café with newspaper racks",
    "the cafe by the station opens early",
    "this cafe roasts on wednesdays",
    "the hardware store sells rope and tar",
)


def _engine(folded: bool) -> Engine:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    for text in DOCUMENTS:
        engine.add({"body": fold(text) if folded else text})
    engine.commit()
    return engine


def _ids(engine: Engine, text: str) -> list[int]:
    return [hit.external for hit in engine.search(text, limit=10).hits]


def run() -> Grade:
    unfolded = _engine(folded=False)
    folded = _engine(folded=True)

    plain_recall = recall(_ids(unfolded, "cafe"), ESPRESSO)
    both_ids = _ids(folded, fold("cafe"))
    both_recall = recall(both_ids, ESPRESSO)
    both_precision = precision(both_ids, ESPRESSO)
    lopsided_recall = recall(_ids(folded, "café"), ESPRESSO)

    holds = (
        plain_recall == 0.5
        and both_recall == 1.0
        and both_precision == 1.0
        and lopsided_recall == 0.0
    )
    return Grade(
        eval_name="foldgain",
        sentence=(
            "folding both sides doubles accent recall for free; "
            "folding one side sends accented queries to zero"
        ),
        numbers={
            "plain_recall": plain_recall,
            "folded_recall": both_recall,
            "folded_precision": both_precision,
            "one_sided_recall": lopsided_recall,
        },
        holds=holds,
    )
