"""Related-term expansion over a co-occurrence graph, depth-capped.

Synonym rings need a human to declare them; the co-occurrence
graph grows its own edges from the corpus: two terms that appear
in the same documents more often than their popularity explains
are related, with the strength scored by a plain Jaccard overlap
of their document sets so frequent words do not buy centrality.
Expansion walks the graph breadth-first from the query term with
two hard fences: depth is capped at two hops because a third hop
connects everything to everything, and each hop multiplies the
edge weight so a friend of a friend arrives discounted, never
equal. The walk returns its paths, not just its terms, because
an expansion that cannot say why it added a word is a synonym
ring with amnesia.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

EDGE_FLOOR = 0.25
MAX_DEPTH = 2


@dataclass(frozen=True)
class Expansion:
    term: str
    weight: float
    path: tuple[str, ...]

    def line(self) -> str:
        route = " -> ".join(self.path)
        return f"{self.term} at {self.weight} (via {route})"


@dataclass
class CooccurrenceGraph:
    doc_sets: dict[str, frozenset[int]] = field(default_factory=dict)

    def learn(self, doc: int, terms: set[str]) -> None:
        for term in terms:
            held = self.doc_sets.get(term, frozenset())
            self.doc_sets[term] = held | {doc}

    def edge(self, left: str, right: str) -> float:
        left_docs = self.doc_sets.get(left, frozenset())
        right_docs = self.doc_sets.get(right, frozenset())
        union = left_docs | right_docs
        if not union:
            return 0.0
        return round(len(left_docs & right_docs) / len(union), 4)

    def neighbors(self, term: str) -> list[tuple[str, float]]:
        found = []
        for other in self.doc_sets:
            if other == term:
                continue
            strength = self.edge(term, other)
            if strength >= EDGE_FLOOR:
                found.append((other, strength))
        found.sort(key=lambda pair: (-pair[1], pair[0]))
        return found

    def expand(
        self, term: str, limit: int = 5
    ) -> list[Expansion]:
        if limit <= 0:
            raise Invalid("an expansion of zero terms expands nothing")
        if term not in self.doc_sets:
            return []
        best: dict[str, Expansion] = {}
        frontier: list[Expansion] = [
            Expansion(term=term, weight=1.0, path=(term,))
        ]
        for _ in range(MAX_DEPTH):
            next_frontier: list[Expansion] = []
            for held in frontier:
                for other, strength in self.neighbors(held.term):
                    if other == term:
                        continue
                    weight = round(held.weight * strength, 4)
                    if weight < EDGE_FLOOR / 2:
                        continue
                    standing = best.get(other)
                    if standing is None or weight > standing.weight:
                        grown = Expansion(
                            term=other,
                            weight=weight,
                            path=(*held.path, other),
                        )
                        best[other] = grown
                        next_frontier.append(grown)
            frontier = next_frontier
        ranked = sorted(
            best.values(),
            key=lambda held: (-held.weight, held.term),
        )
        return ranked[:limit]

    def why(self, term: str, expansion: str) -> str:
        for held in self.expand(term, limit=50):
            if held.term == expansion:
                return held.line()
        return (
            f"{expansion} is not reachable from {term} within "
            f"{MAX_DEPTH} hops above the floor"
        )
