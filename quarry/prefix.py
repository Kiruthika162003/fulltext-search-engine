"""Prefix queries: the vocabulary is sorted, so walk it, do not scan it.

A prefix query like net* expands to every vocabulary term with the
prefix, found by binary search for the prefix's floor and a walk
until the prefix stops holding, which costs the width of the match
band and not the vocabulary. Two guardrails keep the feature from
becoming a denial of service wearing a wildcard. Expansion is
capped and an over-wide prefix is refused with the count, because
e* on a real corpus expands to half the language and the user
almost never meant that. And the leading wildcard is refused
outright: *ing cannot use the sorted order, degrades to a full
vocabulary scan, and the refusal names the reverse-field trick as
the actual fix rather than pretending the scan is fine.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.postings import union
from quarry.segment import Segment

EXPANSION_CAP = 32


@dataclass(frozen=True)
class PrefixExpansion:
    prefix: str
    terms: tuple[str, ...]
    band_width: int
    vocabulary_size: int


def expand_prefix(
    segment: Segment,
    field_name: str,
    prefix: str,
    cap: int = EXPANSION_CAP,
) -> PrefixExpansion:
    if not prefix:
        raise Invalid("an empty prefix matches the whole language")
    if prefix.startswith("*"):
        raise Invalid(
            "a leading wildcard cannot use the sorted vocabulary and "
            "degrades to a full scan; index a reversed field and "
            "prefix-search that instead"
        )
    if cap <= 0:
        raise Invalid("an expansion cap of zero expands nothing")
    vocabulary = segment.vocabulary(field_name)
    floor = bisect_left(vocabulary, prefix)
    matched = []
    cursor = floor
    while cursor < len(vocabulary) and vocabulary[cursor].startswith(
        prefix
    ):
        matched.append(vocabulary[cursor])
        cursor += 1
    if len(matched) > cap:
        raise Invalid(
            f"{prefix}* expands to {len(matched)} terms, past the cap "
            f"of {cap}; a wider prefix is a scan wearing a wildcard"
        )
    return PrefixExpansion(
        prefix=prefix,
        terms=tuple(matched),
        band_width=cursor - floor,
        vocabulary_size=len(vocabulary),
    )


def prefix_docs(
    segment: Segment,
    field_name: str,
    prefix: str,
    cap: int = EXPANSION_CAP,
) -> list[int]:
    expansion = expand_prefix(segment, field_name, prefix, cap)
    docs: list[int] = []
    for term in expansion.terms:
        held = segment.postings_for(field_name, term)
        docs = union(docs, held.docs())
    return docs


def expansion_report(expansion: PrefixExpansion) -> str:
    walked_share = (
        expansion.band_width / expansion.vocabulary_size
        if expansion.vocabulary_size
        else 0.0
    )
    return (
        f"{expansion.prefix}*: {len(expansion.terms)} term(s), walked "
        f"{walked_share:.1%} of the vocabulary instead of all of it"
    )
