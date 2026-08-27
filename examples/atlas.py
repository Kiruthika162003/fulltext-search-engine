"""An afternoon in the atlas: taxonomy, cascade, fusion, and a trace.

Run with: python -m examples.atlas
"""

from __future__ import annotations

from quarry.cascadesearch import cascade
from quarry.fusion import fuse
from quarry.taxonomy import Taxonomy
from quarry.tracing import Span


def build_shelves() -> Taxonomy:
    tree = Taxonomy()
    tree.file_document(0, "maps/nautical")
    tree.file_document(1, "maps/nautical")
    tree.file_document(2, "maps/celestial")
    tree.file_document(3, "maps")
    tree.file_document(4, "atlases/road")
    return tree


def main() -> int:
    tree = build_shelves()
    print(tree.shelf_or_navigation("maps"))
    print(tree.shelf_or_navigation("maps/nautical"))

    page = cascade(
        {
            "exact": lambda: [0],
            "loosened": lambda: [0, 1, 2],
            "fuzzy": lambda: [0, 1, 2, 4],
        },
        floor=3,
    )
    print(page.line())
    print(page.banner())

    fused = fuse(
        {
            "lexical": [1, 0, 2],
            "links": [0, 1, 4],
            "recency": [0, 2, 1],
        }
    )
    print(f"fusion winner: doc {fused[0].external} "
          f"({fused[0].lists_voting} lists)")

    root = Span(name="atlas-search", start=0)
    lookup = root.child("retrieve", 2)
    lookup.finish(40)
    rank = root.child("fuse", 40)
    rank.finish(52)
    root.finish(60)
    print(root.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
