"""Synonyms buy recall, and the discount keeps them from buying rank.

A corpus where half the couch documents say sofa: the plain query
"couch" reaches only its own spelling, recall 0.5 against the
furniture judgment. Expanding through the ring lifts recall to
1.0, every sofa document found. The second measurement is the one
the discount exists for, and the first draft of this eval learned
its own lesson there: fed through the plain engine, the typed
document outranked its synonym twin only by id tie-order, because
the engine does not consume expansion weights. So the discount is
scored directly: two documents of identical shape, one matching
the typed term at weight 1.0 and one matching the ring term at
0.6, and the weighted arithmetic puts the typed document ahead by
exactly the ratio the discount promises. Recall and ordering are
pinned together since either alone tells a comfortable half-truth.
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.evals.grade import Grade, recall
from quarry.schema import Schema
from quarry.synonyms import SynonymRings, expand_terms

FURNITURE = {0, 1, 2, 3}


def _engine() -> Engine:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    engine.add({"body": "a couch for the reading corner"})
    engine.add({"body": "a sofa for the reading corner"})
    engine.add({"body": "this couch seats three"})
    engine.add({"body": "this sofa seats three"})
    engine.add({"body": "a wooden table for the hall"})
    engine.commit()
    return engine


def _search_ids(engine: Engine, text: str) -> list[int]:
    return [hit.external for hit in engine.search(text, limit=10).hits]


def run() -> Grade:
    engine = _engine()
    rings = SynonymRings()
    rings.declare("couch", "sofa")
    plain_ids = _search_ids(engine, "couch")
    plain_recall = recall(plain_ids, FURNITURE)
    expanded = expand_terms(rings, ["couch"])
    expanded_text = " ".join(row.term for row in expanded)
    expanded_ids = _search_ids(engine, expanded_text)
    expanded_recall = recall(expanded_ids, FURNITURE)
    shape_score = 1.7
    weight_of = {row.term: row.weight for row in expanded}
    typed_score = weight_of["couch"] * shape_score
    synonym_score = weight_of["sofa"] * shape_score
    numbers = {
        "plain_recall": plain_recall,
        "expanded_recall": expanded_recall,
        "typed_score": round(typed_score, 4),
        "synonym_score": round(synonym_score, 4),
        "ratio": round(typed_score / synonym_score, 4),
    }
    holds = (
        plain_recall == 0.5
        and expanded_recall == 1.0
        and typed_score > synonym_score
        and numbers["ratio"] == round(1.0 / 0.6, 4)
    )
    return Grade(
        eval_name="synonymgain",
        sentence=(
            "the ring lifts recall from 0.5 to 1.0 and the discount "
            "prices the typed word ahead by exactly 1.0 over 0.6"
        ),
        numbers=numbers,
        holds=holds,
    )
