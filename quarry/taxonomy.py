"""A category taxonomy: counts roll up, paths stay unambiguous.

Catalogs organize documents into a tree, and search wants two
things from it: rollup counts, where electronics/audio counts
toward electronics, and unambiguous membership, where a
document files under a full path, never a bare leaf name,
because leaf names collide the moment gardening/tools meets
hardware/tools. Paths are slash-joined from the root, every
ancestor of a filed path springs into being on first use, and
a document may file under several paths but never twice under
one, since double filing inflates every rollup above it. The
tree prints with counts at each node, direct and rolled up
separately, because a category whose rollup dwarfs its direct
count is navigation, not a shelf, and the difference is what
tells the merchandiser which pages need curating.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


def _validate_path(path: str) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in path.split("/"))
    if not path.strip() or any(not part for part in parts):
        raise Invalid(
            f"{path!r} is not a path; paths are slash-joined "
            f"segments with no empties"
        )
    return parts


@dataclass
class Taxonomy:
    filings: dict[str, set[int]] = field(default_factory=dict)

    def file_document(self, external: int, path: str) -> str:
        parts = _validate_path(path)
        joined = "/".join(parts)
        held = self.filings.setdefault(joined, set())
        if external in held:
            raise Invalid(
                f"doc {external} is already filed under {joined}; "
                f"double filing inflates every rollup above it"
            )
        held.add(external)
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            self.filings.setdefault(ancestor, set())
        return f"doc {external} filed under {joined}"

    def direct_count(self, path: str) -> int:
        joined = "/".join(_validate_path(path))
        if joined not in self.filings:
            raise Invalid(
                f"{joined} is not in the taxonomy; nothing was "
                f"ever filed at or under it"
            )
        return len(self.filings[joined])

    def rollup_count(self, path: str) -> int:
        joined = "/".join(_validate_path(path))
        if joined not in self.filings:
            raise Invalid(
                f"{joined} is not in the taxonomy; nothing was "
                f"ever filed at or under it"
            )
        gathered: set[int] = set()
        prefix = joined + "/"
        for held_path, members in self.filings.items():
            if held_path == joined or held_path.startswith(prefix):
                gathered |= members
        return len(gathered)

    def children(self, path: str | None = None) -> list[str]:
        if path is None:
            depth = 1
            prefix = ""
        else:
            joined = "/".join(_validate_path(path))
            prefix = joined + "/"
            depth = len(joined.split("/")) + 1
        return sorted(
            {
                held
                for held in self.filings
                if held.startswith(prefix)
                and len(held.split("/")) == depth
            }
        )

    def shelf_or_navigation(self, path: str) -> str:
        direct = self.direct_count(path)
        rolled = self.rollup_count(path)
        if direct == 0 and rolled > 0:
            return (
                f"{path}: pure navigation, {rolled} document(s) "
                f"all below"
            )
        if rolled > direct * 3:
            return (
                f"{path}: navigation-heavy, {direct} direct vs "
                f"{rolled} rolled up; the landing page needs "
                f"curating"
            )
        return f"{path}: a shelf, {direct} direct of {rolled} total"

    def tree_page(self) -> str:
        if not self.filings:
            return "an empty taxonomy files nothing"
        lines = []
        for path in sorted(self.filings):
            depth = len(path.split("/")) - 1
            direct = len(self.filings[path])
            rolled = self.rollup_count(path)
            indent = "  " * depth
            lines.append(
                f"{indent}{path.split('/')[-1]}: {direct} direct, "
                f"{rolled} rolled up"
            )
        return "\n".join(lines)
