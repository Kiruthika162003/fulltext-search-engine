"""The grand tour: the engine inventories, grades, and admits itself.

Run with: python -m examples.grandtour
"""

from __future__ import annotations

import pathlib

from quarry.coldstart import warming_report
from quarry.evals.registry import EVALS, broken
from quarry.fieldcensus import census_page
from quarry.inventory import gate, read_theses

QUARRY_DIR = str(
    pathlib.Path(__file__).resolve().parent.parent / "quarry"
)


def main() -> int:
    theses = read_theses(QUARRY_DIR)
    print(gate(QUARRY_DIR))
    print(
        f"the shortest thesis: "
        f"{min(theses.values(), key=len)}"
    )

    failing = broken()
    print(
        f"{len(EVALS)} evals in the registry, "
        f"{len(failing)} broken"
    )

    print(
        warming_report(
            {
                "search": 13,
                "snippets": 13,
                "suggestions": 60,
                "relevance-evals": 250,
            }
        ).splitlines()[-1]
    )

    documents = [
        {"body": "a small corpus", "lang": "en"},
        {"body": "ein kleiner korpus", "lang": "de"},
        {"body": "un petit corpus"},
    ]
    print(census_page(documents).splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
