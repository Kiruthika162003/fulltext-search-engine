"""Front coding: the term dictionary stops repeating itself.

A sorted term dictionary is mostly repetition, "search",
"searched", "searcher" sharing their front, and front coding
stores each term as the length of the prefix it shares with
its predecessor plus the fresh suffix. Blocks bound the damage
reading costs: every block starts with a full term so a lookup
decodes at most one block instead of the dictionary, and the
block size is the declared trade between compression and
lookup work. The contracts are the usual ones stated plainly:
input must be sorted and unique because prefix sharing against
an unsorted neighbor stores garbage that decodes cleanly,
which is the worst kind, and lookup answers present or absent
by decoding the one candidate block, never by trusting prefix
arithmetic alone. The savings report measures characters
stored against characters raw, on this dictionary, with the
block overhead counted rather than waved away.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

BLOCK_SIZE = 4


def _shared_front(left: str, right: str) -> int:
    bound = min(len(left), len(right))
    for index in range(bound):
        if left[index] != right[index]:
            return index
    return bound


@dataclass(frozen=True)
class CodedBlock:
    lead: str
    tails: tuple[tuple[int, str], ...]

    def terms(self) -> list[str]:
        out = [self.lead]
        previous = self.lead
        for shared, suffix in self.tails:
            term = previous[:shared] + suffix
            out.append(term)
            previous = term
        return out

    def stored_chars(self) -> int:
        return len(self.lead) + sum(
            len(suffix) for _, suffix in self.tails
        )


def encode_dictionary(terms: list[str]) -> list[CodedBlock]:
    if not terms:
        raise Invalid("an empty dictionary codes nothing")
    for left, right in zip(terms, terms[1:], strict=False):
        if right <= left:
            raise Invalid(
                f"{right!r} after {left!r} is not sorted-unique; "
                f"prefix sharing against the wrong neighbor stores "
                f"garbage that decodes cleanly, the worst kind"
            )
    blocks = []
    for start in range(0, len(terms), BLOCK_SIZE):
        chunk = terms[start : start + BLOCK_SIZE]
        tails = []
        previous = chunk[0]
        for term in chunk[1:]:
            shared = _shared_front(previous, term)
            tails.append((shared, term[shared:]))
            previous = term
        blocks.append(
            CodedBlock(lead=chunk[0], tails=tuple(tails))
        )
    return blocks


def decode_dictionary(blocks: list[CodedBlock]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        out.extend(block.terms())
    return out


def lookup(blocks: list[CodedBlock], term: str) -> bool:
    if not blocks:
        raise Invalid("looking up in no blocks finds nothing")
    candidate = None
    for block in blocks:
        if block.lead <= term:
            candidate = block
        else:
            break
    if candidate is None:
        return False
    return term in candidate.terms()


def savings_report(terms: list[str]) -> str:
    blocks = encode_dictionary(terms)
    raw = sum(len(term) for term in terms)
    stored = sum(block.stored_chars() for block in blocks)
    ratio = raw / stored if stored else 1.0
    return (
        f"{len(terms)} term(s) in {len(blocks)} block(s) of "
        f"{BLOCK_SIZE}: {raw} raw chars -> {stored} stored "
        f"({ratio:.2f}x), block leads counted, not waved away"
    )
