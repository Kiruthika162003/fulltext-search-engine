"""Document links: citations vote, and the votes are weighed.

When documents cite each other, wikis and papers and product
docs all do, the link graph carries a relevance signal the text
does not: a page every other page cites is load-bearing. The
authority score here is the plain iterative kind, every
document starts equal, each round divides a document's score
among its outbound links and collects what others sent, with a
damping share that keeps score from pooling in cycles, run to
a fixed round count with the movement of the last round
reported so the caller can see whether it converged or was
merely stopped. Two graph smells are refused at the door:
self-citations, which are free votes for yourself, and
duplicate edges, which turn one enthusiastic author into a
ballot box. Dangling documents, cited but citing nothing,
spread their score evenly rather than hoarding it, the
standard fix stated plainly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

DAMPING = 0.85
ROUNDS = 20


@dataclass
class LinkGraph:
    outbound: dict[int, set[int]] = field(default_factory=dict)
    documents: set[int] = field(default_factory=set)

    def add_document(self, doc: int) -> None:
        self.documents.add(doc)

    def cite(self, source: int, target: int) -> str:
        if source == target:
            raise Invalid(
                f"doc {source} cites itself; free votes for "
                f"yourself are not votes"
            )
        for doc in (source, target):
            if doc not in self.documents:
                raise Invalid(
                    f"doc {doc} is not in the graph; add documents "
                    f"before their links"
                )
        held = self.outbound.setdefault(source, set())
        if target in held:
            raise Invalid(
                f"doc {source} already cites {target}; one "
                f"enthusiastic author is not a ballot box"
            )
        held.add(target)
        return f"{source} -> {target}"

    def authority(self) -> tuple[dict[int, float], float]:
        if not self.documents:
            raise Invalid("an empty graph has no authority to give")
        count = len(self.documents)
        score = dict.fromkeys(self.documents, 1.0 / count)
        movement = 0.0
        for _ in range(ROUNDS):
            fresh = dict.fromkeys(self.documents, (1.0 - DAMPING) / count)
            for doc in self.documents:
                targets = self.outbound.get(doc, set())
                if not targets:
                    share = DAMPING * score[doc] / count
                    for other in self.documents:
                        fresh[other] += share
                    continue
                share = DAMPING * score[doc] / len(targets)
                for target in targets:
                    fresh[target] += share
            movement = sum(
                abs(fresh[doc] - score[doc])
                for doc in self.documents
            )
            score = fresh
        rounded = {
            doc: round(value, 4) for doc, value in score.items()
        }
        return rounded, round(movement, 6)

    def report(self) -> str:
        scores, movement = self.authority()
        ranked = sorted(
            scores.items(), key=lambda pair: (-pair[1], pair[0])
        )
        lines = [
            f"doc {doc}: {value}" for doc, value in ranked
        ]
        state = (
            "converged"
            if movement < 0.001
            else f"still moving ({movement}); stopped, not settled"
        )
        lines.append(f"after {ROUNDS} rounds: {state}")
        return "\n".join(lines)
