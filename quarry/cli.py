"""The command line: the quality suite and a working search, on demand."""

from __future__ import annotations

import argparse
import sys

from quarry.evals.registry import broken, report


def _demo(text: str) -> int:
    from quarry.evals.corpus import DOCUMENTS, build_engine

    engine = build_engine()
    response = engine.search(text, snippet_fields=("body",))
    print(f"query: {response.canonical}")
    if response.suggestion:
        print(f"did you mean: {response.suggestion}")
    for hit in response.hits:
        line = hit.snippets[0][1] if hit.snippets else DOCUMENTS[hit.external]
        print(f"  [{hit.score:8.4f}] doc {hit.external}: {line}")
    if not response.hits:
        print("  nothing matched")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quarry")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("evals", help="run every eval and print the grades")
    commands.add_parser("check", help="exit nonzero if any eval is broken")
    demo = commands.add_parser(
        "search", help="search the fixture corpus from the shell"
    )
    demo.add_argument("text", help="the query, quarry syntax")
    parsed = parser.parse_args(argv)
    if parsed.command == "evals":
        print(report())
        return 0
    if parsed.command == "search":
        return _demo(parsed.text)
    failing = broken()
    if failing:
        print(f"broken: {', '.join(failing)}")
        return 1
    print("all evals hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
