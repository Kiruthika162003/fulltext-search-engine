"""Near-duplicate detection: the same article wearing three headlines.

Exact duplicates hash identically and cost nothing to find; the
expensive lie is the near-duplicate, the wire story with a swapped
byline that fills page one with one answer five times. Shingling
turns each document into its set of overlapping word windows, the
Jaccard overlap of two shingle sets measures how much prose they
truly share, and a threshold turns the number into a verdict. The
window width is the sensitivity dial and both failure directions
are stated: narrow shingles call paraphrases duplicates, wide
shingles miss reorderings, and the default of three words is the
compromise the tests document with concrete pairs. Clustering is
transitive on purpose, because if A matches B and B matches C, the
reader does not care that A and C drifted below the line: it is
one story, shown once, with its variants listed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

SHINGLE_WIDTH = 3
DUPLICATE_LINE = 0.6


def shingles(
    text: str, analyzer: Analyzer, width: int = SHINGLE_WIDTH
) -> set[tuple[str, ...]]:
    if width < 1:
        raise Invalid("a shingle needs at least one word")
    terms = analyzer.terms(text)
    if len(terms) < width:
        return {tuple(terms)} if terms else set()
    return {
        tuple(terms[index : index + width])
        for index in range(len(terms) - width + 1)
    }


def jaccard(left: set, right: set) -> float:
    if not left and not right:
        raise Invalid(
            "two empty sets overlap by convention, not by measurement; "
            "refuse to guess"
        )
    joined = len(left | right)
    return round(len(left & right) / joined, 4)


@dataclass(frozen=True)
class DuplicatePair:
    left: int
    right: int
    overlap: float


@dataclass
class DuplicateFinder:
    analyzer: Analyzer = field(default_factory=Analyzer)
    width: int = SHINGLE_WIDTH
    line: float = DUPLICATE_LINE
    held: dict[int, set[tuple[str, ...]]] = field(default_factory=dict)

    def admit(self, external: int, text: str) -> None:
        if external in self.held:
            raise Invalid(f"doc {external} was already admitted")
        self.held[external] = shingles(text, self.analyzer, self.width)

    def pairs(self) -> list[DuplicatePair]:
        found = []
        ids = sorted(self.held)
        for position, left in enumerate(ids):
            for right in ids[position + 1 :]:
                left_set = self.held[left]
                right_set = self.held[right]
                if not left_set and not right_set:
                    continue
                overlap = jaccard(left_set, right_set)
                if overlap >= self.line:
                    found.append(
                        DuplicatePair(
                            left=left, right=right, overlap=overlap
                        )
                    )
        return found

    def clusters(self) -> list[list[int]]:
        """Transitive grouping: one story, shown once, variants listed."""
        parent: dict[int, int] = {external: external for external in self.held}

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for pair in self.pairs():
            left_root, right_root = find(pair.left), find(pair.right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(
                    left_root, right_root
                )
        grouped: dict[int, list[int]] = {}
        for external in sorted(self.held):
            grouped.setdefault(find(external), []).append(external)
        return [members for _, members in sorted(grouped.items())]

    def representatives(self) -> list[int]:
        """One document per cluster: the lowest id, the first seen."""
        return [members[0] for members in self.clusters()]

    def collapse_report(self) -> str:
        clusters = self.clusters()
        collapsed = sum(len(members) - 1 for members in clusters)
        lines = [
            f"{len(self.held)} documents, {len(clusters)} stories, "
            f"{collapsed} hidden as variants"
        ]
        for members in clusters:
            if len(members) > 1:
                variants = ", ".join(str(m) for m in members[1:])
                lines.append(f"  doc {members[0]} speaks for {variants}")
        return "\n".join(lines)
