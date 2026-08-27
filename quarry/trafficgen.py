"""Synthetic traffic: load tests speak the corpus's own language.

A load test firing random strings measures the zero-result
path and nothing else, so the generator builds queries from
the vocabulary under test, sampled by a Zipf-shaped rank
distribution because real query traffic is a few heads and a
long tail, and the shape parameter is declared so two load
tests are comparable. Determinism is the second requirement:
the same seed must produce the same traffic, replayable when a
regression needs the exact sequence that broke things, so
sampling runs on a hash-mixed counter rather than a random
module that changes across versions. The mix is declared per
run, single terms, AND pairs, and phrases in stated shares,
and the generator reports the mix it actually produced beside
the mix that was asked for, because rounding on small runs
drifts and the report should say so before someone else
measures it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid

DEFAULT_SHAPE = 1.2


def _mix_value(seed: str, counter: int) -> float:
    digest = hashlib.sha256(
        f"{seed}|{counter}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def zipf_pick(
    vocabulary: list[str], roll: float, shape: float
) -> str:
    if not vocabulary:
        raise Invalid("an empty vocabulary generates nothing")
    weights = [
        1.0 / (rank**shape)
        for rank in range(1, len(vocabulary) + 1)
    ]
    total = sum(weights)
    cursor = roll * total
    for word, weight in zip(vocabulary, weights, strict=True):
        cursor -= weight
        if cursor <= 0:
            return word
    return vocabulary[-1]


@dataclass(frozen=True)
class TrafficMix:
    single_share: float
    pair_share: float
    phrase_share: float

    def __post_init__(self) -> None:
        total = (
            self.single_share + self.pair_share + self.phrase_share
        )
        if abs(total - 1.0) > 1e-9:
            raise Invalid(
                f"the mix sums to {total}, not 1.0; the missing "
                f"share would be invented silently"
            )


@dataclass(frozen=True)
class GeneratedTraffic:
    queries: tuple[str, ...]
    asked_mix: TrafficMix
    produced: dict[str, int]

    def report(self) -> str:
        total = len(self.queries)
        lines = [f"{total} queries generated"]
        for kind in ("single", "pair", "phrase"):
            count = self.produced.get(kind, 0)
            lines.append(
                f"  {kind}: {count} ({count / total:.0%})"
            )
        lines.append(
            "produced shares drift from asked shares on small "
            "runs; compare before quoting"
        )
        return "\n".join(lines)


def generate(
    vocabulary: list[str],
    count: int,
    seed: str,
    mix: TrafficMix,
    shape: float = DEFAULT_SHAPE,
) -> GeneratedTraffic:
    if count <= 0:
        raise Invalid("generating zero queries tests nothing")
    if len(vocabulary) < 2:
        raise Invalid(
            "a vocabulary of one word generates one query forever"
        )
    queries: list[str] = []
    produced = {"single": 0, "pair": 0, "phrase": 0}
    for n in range(count):
        kind_roll = _mix_value(seed, n * 3)
        first = zipf_pick(
            vocabulary, _mix_value(seed, n * 3 + 1), shape
        )
        second = zipf_pick(
            vocabulary, _mix_value(seed, n * 3 + 2), shape
        )
        if kind_roll < mix.single_share:
            queries.append(f"body:{first}")
            produced["single"] += 1
        elif kind_roll < mix.single_share + mix.pair_share:
            queries.append(f"+body:{first} +body:{second}")
            produced["pair"] += 1
        else:
            queries.append(f'"{first} {second}"')
            produced["phrase"] += 1
    return GeneratedTraffic(
        queries=tuple(queries),
        asked_mix=mix,
        produced=produced,
    )
