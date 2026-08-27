"""An hour in the code index: identifiers split, exact spellings win.

Run with: python -m examples.codesearch
"""

from __future__ import annotations

from quarry.engine import Engine
from quarry.schema import Schema
from quarry.subwords import expand_token, split_report

FUNCTIONS = [
    ("getUserName", "auth/session.py", "returns the display name"),
    ("get_user_id", "auth/session.py", "returns the numeric id"),
    ("HTTPResponseCache", "net/cache.py", "memoizes whole responses"),
    ("parseConfigFile", "boot/config.py", "reads the startup config"),
    ("renameUser", "admin/users.py", "changes the display name"),
    ("purgeStaleCache", "net/cache.py", "drops expired entries"),
]


def identifier_text(identifier: str) -> str:
    """The whole spelling plus its parts, one indexable string."""
    return " ".join(expand_token(identifier))


def build_code_index() -> Engine:
    schema = Schema()
    schema.add_text("symbol")
    schema.add_text("doc")
    schema.add_keyword("path")
    schema.seal()
    engine = Engine(schema=schema)
    for identifier, path, doc in FUNCTIONS:
        engine.add(
            {
                "symbol": identifier_text(identifier),
                "doc": doc,
                "path": path,
            }
        )
    engine.commit()
    return engine


def search_symbols(engine: Engine, text: str) -> list[str]:
    scoped = " ".join(f"symbol:{term}" for term in expand_token(text))
    response = engine.search(scoped)
    names = []
    for hit in response.hits:
        names.append(FUNCTIONS[hit.external][0])
    return names


def main() -> int:
    engine = build_code_index()

    print("how the splitter reads the identifiers:")
    for row in split_report([name for name, _, _ in FUNCTIONS]).splitlines():
        print(f"  {row}")

    for query in ("user", "cache", "getUserName"):
        found = search_symbols(engine, query)
        print(f"query {query!r} finds: {', '.join(found) if found else 'nothing'}")

    exact = search_symbols(engine, "getUserName")
    print(f"exact spelling ranks first: {exact[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
