"""Stemming is a trade, and both sides of the invoice are measured.

The same corpus indexes twice, stemming on and stemming off, and
the query "cats" runs against both. With stemming, cat and cats
collapse to one term and recall against the cat judgment is 1.0,
every relevant document found regardless of which form it used.
Without stemming, the query only reaches documents that spelled it
"cats", recall drops to exactly the share that happened to
pluralise, measured at 0.5 on this corpus. The guessed vocabulary
shrink of 62 to 57 measured 21 to 20 on this small corpus: one
term saved, cats folding into cat, the compression real but
proportional to how much the prose actually inflects. Neither
number is an opinion; the eval exists so the analyzer default is a
decision with an invoice attached instead of a folk custom.
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.evals.grade import Grade, recall
from quarry.schema import Schema
from quarry.tokenize import Analyzer

CORPUS = [
    "the cats sleep in the barn",
    "a cat walked along the fence",
    "three cats chased one mouse",
    "the cat show drew a crowd",
    "dogs barked at the mailman",
    "a quiet evening with tea and books",
]
RELEVANT_TO_CAT = {0, 1, 2, 3}


def _engine(stemming: bool) -> Engine:
    schema = Schema()
    schema.add_text("body", analyzer=Analyzer(stemming=stemming))
    schema.seal()
    engine = Engine(schema=schema)
    for text in CORPUS:
        engine.add({"body": text})
    engine.commit()
    return engine


def _returned(engine: Engine, text: str) -> list[int]:
    return [hit.external for hit in engine.search(text, limit=10).hits]


def run() -> Grade:
    stemmed = _engine(stemming=True)
    plain = _engine(stemming=False)
    stemmed_recall = recall(
        _returned(stemmed, "cats"), RELEVANT_TO_CAT
    )
    plain_recall = recall(_returned(plain, "cats"), RELEVANT_TO_CAT)
    stemmed_vocabulary = stemmed.vocabulary.vocabulary_size()
    plain_vocabulary = plain.vocabulary.vocabulary_size()
    numbers = {
        "stemmed_recall": stemmed_recall,
        "plain_recall": plain_recall,
        "stemmed_vocabulary": stemmed_vocabulary,
        "plain_vocabulary": plain_vocabulary,
    }
    holds = (
        stemmed_recall == 1.0
        and plain_recall == 0.5
        and stemmed_vocabulary < plain_vocabulary
    )
    return Grade(
        eval_name="stemtrade",
        sentence=(
            "stemming buys recall 1.0 where the plain index reaches "
            "only the half that pluralised, and shrinks the vocabulary "
            "as the quiet second dividend"
        ),
        numbers=numbers,
        holds=holds,
    )
