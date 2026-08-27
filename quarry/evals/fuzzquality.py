"""Fuzzy matching earns its candidates and refuses its impostors.

The fuzzy index answers misspellings with dictionary words, and
its quality is two numbers that pull against each other: the
hit rate on genuine one-slip typos, which should be high
because those are the errors people actually make, and the
false-friend rate on real words that happen to sit one edit
from other real words, which should stay low because
correcting a word the user meant is worse than missing a typo.
The fixture builds both sets from one vocabulary: every typo is
a single adjacent-key slip on a real word, every false friend
is itself a vocabulary word, and the eval demands the suggester
find the intended word for at least four of five typos while
never outranking a real typed word with a neighbor, since the
suggestion floor exists precisely to keep corrections behind
exact matches.
"""

from __future__ import annotations

from quarry.evals.grade import Grade
from quarry.fuzzy import FuzzyIndex, did_you_mean, suggest

VOCABULARY = {
    "kettle": 40,
    "settle": 25,
    "copper": 30,
    "stove": 20,
    "blanket": 15,
}

TYPOS = (
    ("kwttle", "kettle"),
    ("coppwr", "copper"),
    ("stovr", "stove"),
    ("blanmet", "blanket"),
    ("settke", "settle"),
)


def _index() -> FuzzyIndex:
    index = FuzzyIndex()
    for word, weight in VOCABULARY.items():
        index.admit(word, weight=weight)
    return index


def run() -> Grade:
    index = _index()
    found = 0
    for typed, intended in TYPOS:
        held = suggest(index, typed, limit=3)
        if intended in [one.term for one in held]:
            found += 1
    hit_rate = round(found / len(TYPOS), 4)

    false_friends = sum(
        1
        for real in VOCABULARY
        if did_you_mean(index, real) is not None
    )
    friend_rate = round(false_friends / len(VOCABULARY), 4)

    holds = hit_rate >= 0.8 and friend_rate == 0.0
    return Grade(
        eval_name="fuzzquality",
        sentence=(
            "one-slip typos find their word and real words are "
            "never outranked by their neighbors"
        ),
        numbers={
            "typo_hit_rate": hit_rate,
            "false_friend_rate": friend_rate,
            "typos_tested": len(TYPOS),
        },
        holds=holds,
    )
