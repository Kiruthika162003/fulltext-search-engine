"""Duplicate clustering: pairwise verdicts become families, carefully.

Duplicate detection emits pairs, A matches B, B matches C, and
the catalog question is families: which documents are one
listing wearing several ids. Union-find with path compression
turns pairs into components cheaply, and the module carries
the two disciplines the naive version forgets. Transitivity is
a decision, not a fact: A-B and B-C joining A to C is exactly
what union-find does, so joins below the declared confidence
are refused at the door rather than diluted in, because one
weak pair welds two honest families into a chimera that no
threshold can cut apart afterward. And every family elects a
canonical representative deterministically, the smallest id,
so re-running the clustering names the same survivors and the
dedupe suppressions are stable across days instead of
flickering as dict order shifts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

JOIN_FLOOR = 0.7


@dataclass
class DupClusters:
    parent: dict[int, int] = field(default_factory=dict)
    joins: int = 0
    refused: int = 0

    def _find(self, doc: int) -> int:
        root = doc
        while self.parent.get(root, root) != root:
            root = self.parent[root]
        while self.parent.get(doc, doc) != root:
            doc, self.parent[doc] = self.parent[doc], root
        return root

    def join(
        self, left: int, right: int, confidence: float
    ) -> str:
        if not 0.0 <= confidence <= 1.0:
            raise Invalid("confidence lives in [0, 1]")
        if left == right:
            raise Invalid(
                f"doc {left} cannot duplicate itself; identity is "
                f"not similarity"
            )
        if confidence < JOIN_FLOOR:
            self.refused += 1
            return (
                f"refused at {confidence}: one weak pair welds "
                f"two honest families into a chimera"
            )
        self.parent.setdefault(left, left)
        self.parent.setdefault(right, right)
        left_root = self._find(left)
        right_root = self._find(right)
        if left_root == right_root:
            return "already family"
        winner = min(left_root, right_root)
        loser = max(left_root, right_root)
        self.parent[loser] = winner
        self.joins += 1
        return f"joined under {winner}"

    def canonical(self, doc: int) -> int:
        if doc not in self.parent:
            return doc
        return self._find(doc)

    def families(self) -> list[list[int]]:
        by_root: dict[int, list[int]] = {}
        for doc in self.parent:
            by_root.setdefault(self._find(doc), []).append(doc)
        return sorted(
            sorted(members)
            for members in by_root.values()
            if len(members) > 1
        )

    def suppressions(self) -> list[int]:
        out = []
        for family in self.families():
            out.extend(family[1:])
        return sorted(out)

    def report(self) -> str:
        families = self.families()
        if not families:
            return (
                f"no families; {self.refused} weak pair(s) "
                f"refused at the door"
            )
        lines = []
        for family in families:
            members = ", ".join(str(doc) for doc in family[1:])
            lines.append(
                f"family of {len(family)} under doc {family[0]}; "
                f"suppress {members}"
            )
        lines.append(
            f"{self.joins} join(s), {self.refused} refused below "
            f"{JOIN_FLOOR}"
        )
        return "\n".join(lines)
