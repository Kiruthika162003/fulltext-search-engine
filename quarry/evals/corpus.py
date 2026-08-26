"""The fixture corpus: small enough to read, real enough to argue with.

Thirteen documents about animals, instruments, and weather, written
so the interesting retrieval questions have known right answers: a
rare term that should dominate ranking, a phrase that appears in
exactly two documents, a stopword-heavy sentence that tests the
pipeline, a pair of duplicates that tests tie handling, and one
document where black and cat co-occur without touching, the false
friend every phrase eval needs.
Every eval builds on this corpus so their numbers stay comparable,
and the relevance judgments live beside the text as plain sets,
because a judgment hidden in a helper is a judgment nobody reviews.
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.schema import Schema

DOCUMENTS = [
    "the black cat sat quietly on the warm mat",
    "a black dog chased the black cat through rain",
    "cats and dogs living together in one house",
    "the quiet xylophone player practised at dawn",
    "a marching band with drums and one xylophone",
    "heavy rain fell on the city all night long",
    "the weather report promised rain and cold wind",
    "a cat show with many cats of every colour",
    "dogs bark and cats nap, such is the house",
    "the black cat returned to the warm cellar",
    "identical twin sentence about gentle weather",
    "identical twin sentence about gentle weather",
    "black paint dried while the cat slept elsewhere",
]

RELEVANT_TO_CAT = {0, 1, 2, 7, 8, 9, 12}
RELEVANT_TO_XYLOPHONE = {3, 4}
RELEVANT_TO_BLACK_CAT_PHRASE = {0, 1, 9}
RELEVANT_TO_RAIN = {1, 5, 6}


def build_engine() -> Engine:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    for text in DOCUMENTS:
        engine.add({"body": text})
    engine.commit()
    return engine


def returned_ids(engine: Engine, text: str, limit: int = 10) -> list[int]:
    return [
        hit.external for hit in engine.search(text, limit=limit).hits
    ]
