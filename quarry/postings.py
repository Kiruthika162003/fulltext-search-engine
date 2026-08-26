"""Postings: the index is a phone book, and this is one entry.

A posting list answers "which documents contain this term, where,
and how often" in document-id order, because sorted order is what
makes intersection linear and union a merge instead of a shuffle.
Positions ride along per document so phrase queries can align them
without a second lookup, and the frequency is stored rather than
recomputed since ranking will ask for it on every query while the
positions are only consulted when a phrase demands proof. The
operations here are the whole query algebra in miniature: AND is
intersection, OR is union, NOT is difference against a universe,
and a phrase is intersection plus an alignment check, all of them
walking two sorted lists the way a zipper closes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass(frozen=True)
class Posting:
    doc: int
    positions: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.positions:
            raise Invalid(
                f"doc {self.doc}: a posting with no positions claims a "
                f"term that appears nowhere"
            )
        if list(self.positions) != sorted(set(self.positions)):
            raise Invalid(
                f"doc {self.doc}: positions must be strictly increasing"
            )

    @property
    def frequency(self) -> int:
        return len(self.positions)


@dataclass
class PostingList:
    term: str
    rows: list[Posting] = field(default_factory=list)

    def add(self, doc: int, positions: tuple[int, ...]) -> None:
        if self.rows and doc <= self.rows[-1].doc:
            raise Invalid(
                f"{self.term}: doc {doc} arrived out of order after "
                f"{self.rows[-1].doc}; posting lists are append-only "
                f"and sorted"
            )
        self.rows.append(Posting(doc=doc, positions=positions))

    def docs(self) -> list[int]:
        return [row.doc for row in self.rows]

    def document_frequency(self) -> int:
        return len(self.rows)

    def find(self, doc: int) -> Posting | None:
        low, high = 0, len(self.rows)
        while low < high:
            middle = (low + high) // 2
            if self.rows[middle].doc < doc:
                low = middle + 1
            else:
                high = middle
        if low < len(self.rows) and self.rows[low].doc == doc:
            return self.rows[low]
        return None


def intersect(left: list[int], right: list[int]) -> list[int]:
    out: list[int] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            out.append(left[i])
            i += 1
            j += 1
        elif left[i] < right[j]:
            i += 1
        else:
            j += 1
    return out


def union(left: list[int], right: list[int]) -> list[int]:
    out: list[int] = []
    i = j = 0
    while i < len(left) or j < len(right):
        if j >= len(right) or (i < len(left) and left[i] < right[j]):
            candidate = left[i]
            i += 1
        elif i >= len(left) or right[j] < left[i]:
            candidate = right[j]
            j += 1
        else:
            candidate = left[i]
            i += 1
            j += 1
        if not out or out[-1] != candidate:
            out.append(candidate)
    return out


def difference(universe: list[int], excluded: list[int]) -> list[int]:
    out: list[int] = []
    j = 0
    for doc in universe:
        while j < len(excluded) and excluded[j] < doc:
            j += 1
        if j < len(excluded) and excluded[j] == doc:
            continue
        out.append(doc)
    return out


def phrase_docs(lists: list[PostingList]) -> list[int]:
    """Documents where the terms appear at consecutive positions.

    The alignment trick: shift each term's positions left by its
    index in the phrase, and a phrase occurrence becomes a position
    all terms share. Intersection of small sets after shifting is
    cheaper than sliding windows, and reads like the definition.
    """
    if not lists:
        raise Invalid("an empty phrase matches nothing and means less")
    candidates = lists[0].docs()
    for held in lists[1:]:
        candidates = intersect(candidates, held.docs())
    matched: list[int] = []
    for doc in candidates:
        shifted: set[int] | None = None
        for offset, held in enumerate(lists):
            posting = held.find(doc)
            positions = {
                position - offset for position in posting.positions
            }
            shifted = (
                positions if shifted is None else shifted & positions
            )
            if not shifted:
                break
        if shifted:
            matched.append(doc)
    return matched
