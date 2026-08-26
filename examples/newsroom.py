"""A morning at the wire desk: dedup, alerts, and the day's briefing.

Run with: python -m examples.newsroom
"""

from __future__ import annotations

from quarry.duplicates import DuplicateFinder
from quarry.percolate import Percolator
from quarry.querylog import QueryLog
from quarry.schema import Schema

WIRE = [
    "council approves the new bridge budget after long funding debate",
    "council approves the new bridge budget after long funding talks",
    "storm warning issued as heavy rain approaches the coast",
    "local bakery wins the regional sourdough prize",
]


def wire_desk() -> tuple[Percolator, DuplicateFinder]:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    percolator = Percolator(schema=schema)
    percolator.subscribe("bridge-watch", "bridge budget")
    percolator.subscribe("storm-watch", '"heavy rain"')
    return percolator, DuplicateFinder()


def main() -> int:
    percolator, finder = wire_desk()
    for number, story in enumerate(WIRE):
        finder.admit(number, story)
        fired = percolator.percolate({"body": story})
        if fired.fired:
            names = ", ".join(fired.fired)
            print(f"story {number} fires: {names}")
    print(finder.collapse_report())

    log = QueryLog()
    for session in ("a", "b", "c"):
        log.log(session, "bridge collapse", results=0, clicked=False)
        log.log(session, "bridge budget", results=2, clicked=True)
    print(log.briefing())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
