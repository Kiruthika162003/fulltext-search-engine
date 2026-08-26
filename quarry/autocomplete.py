"""Autocomplete: the prefix trie answers before the user finishes.

Completion is a different data structure because it is a different
question: not "which documents contain this term" but "which terms
continue this prefix, weighted by how much anyone wants them". The
trie stores one node per character with a popularity total per
terminal, lookups walk the prefix then collect the subtree, and
the top-k cut happens after collection with ties alphabetical so
the dropdown never reshuffles between keystrokes that add no
information. Weights come from wherever the caller trusts, query
logs usually, and decay is the caller's job, because a completion
engine that quietly ages its own weights is making editorial calls
nobody asked it to make. The empty prefix is refused: completing
nothing is a popularity chart, and there is a method for that with
an honest name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass
class TrieNode:
    children: dict[str, TrieNode] = field(default_factory=dict)
    terminal_weight: int = 0


@dataclass(frozen=True)
class Completion:
    term: str
    weight: int


@dataclass
class Completer:
    root: TrieNode = field(default_factory=TrieNode)
    terms_held: int = 0

    def admit(self, term: str, weight: int = 1) -> None:
        if not term:
            raise Invalid("an empty term completes nothing")
        if weight <= 0:
            raise Invalid(f"{term!r}: weight must be positive")
        node = self.root
        for char in term:
            node = node.children.setdefault(char, TrieNode())
        if node.terminal_weight == 0:
            self.terms_held += 1
        node.terminal_weight += weight

    def _walk(self, prefix: str) -> TrieNode | None:
        node = self.root
        for char in prefix:
            node = node.children.get(char)
            if node is None:
                return None
        return node

    def _collect(
        self, node: TrieNode, built: str, out: list[Completion]
    ) -> None:
        if node.terminal_weight > 0:
            out.append(Completion(term=built, weight=node.terminal_weight))
        for char in sorted(node.children):
            self._collect(node.children[char], built + char, out)

    def complete(self, prefix: str, limit: int = 5) -> list[Completion]:
        if not prefix:
            raise Invalid(
                "completing the empty prefix is a popularity chart; "
                "call popular() and say what you mean"
            )
        if limit <= 0:
            raise Invalid("a dropdown with no rows should not open")
        node = self._walk(prefix)
        if node is None:
            return []
        found: list[Completion] = []
        self._collect(node, prefix, found)
        found.sort(key=lambda held: (-held.weight, held.term))
        return found[:limit]

    def popular(self, limit: int = 5) -> list[Completion]:
        if limit <= 0:
            raise Invalid("a chart with no rows should not print")
        found: list[Completion] = []
        self._collect(self.root, "", found)
        found.sort(key=lambda held: (-held.weight, held.term))
        return found[:limit]

    def prefix_exists(self, prefix: str) -> bool:
        return self._walk(prefix) is not None


def stable_between_keystrokes(
    completer: Completer, prefix: str, limit: int = 5
) -> bool:
    """Adding a character that all top results share must not reshuffle.

    The dropdown property users actually notice: typing the next
    letter of the current top suggestion should refine, never
    reorder what remains. Verified rather than assumed because the
    tie rules are exactly where implementations quietly break it.
    """
    before = completer.complete(prefix, limit)
    if not before:
        return True
    survivors = [
        held for held in before if held.term.startswith(before[0].term[: len(prefix) + 1])
    ]
    after = completer.complete(before[0].term[: len(prefix) + 1], limit)
    after_terms = [held.term for held in after]
    survivor_terms = [held.term for held in survivors]
    return all(
        after_terms.index(a) <= after_terms.index(b)
        for a, b in zip(survivor_terms, survivor_terms[1:], strict=False)
        if a in after_terms and b in after_terms
    )
