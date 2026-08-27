"""Query repair: broken syntax mended in the open, never silently.

Users paste queries with unbalanced quotes, trailing operators,
and stray colons, and the two wrong responses are the error
page, which punishes a typo with a dead end, and the silent
fix, which searches for something other than what was typed
without saying so. The repairer sits between: each mend is a
named rule, close the unclosed quote at the end of the input,
drop the operator with nothing on its right, strip the colon
that has no field before it, and the repaired query ships WITH
the list of mends so the interface can say searched for this
instead. Repairs never touch a query that parses, a mend that
still fails to parse falls through to the honest error rather
than recursing into creative rewriting, and the mend count is
capped because an input needing five repairs is not a query
with typos, it is noise wearing a query's shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, QuarryError
from quarry.query import Query, parse

MEND_CAP = 2


@dataclass(frozen=True)
class Repair:
    query: Query
    mends: tuple[str, ...]

    def narrated(self) -> str:
        if not self.mends:
            return "parsed as typed"
        listed = "; ".join(self.mends)
        return f"searched with repairs: {listed}"


def _mend_once(text: str) -> tuple[str, str] | None:
    if text.count('"') % 2 == 1:
        return (
            text + '"',
            "closed the unclosed quote at the end",
        )
    stripped = text.rstrip()
    for operator in ("OR", "+", "-"):
        if stripped.endswith(operator) and len(stripped) > len(operator):
            return (
                stripped[: -len(operator)].rstrip(),
                f"dropped the trailing {operator} with nothing "
                f"on its right",
            )
    pieces = stripped.split()
    for index, piece in enumerate(pieces):
        if piece.startswith(":"):
            mended = pieces[:index] + [piece.lstrip(":")] + pieces[index + 1 :]
            return (
                " ".join(part for part in mended if part),
                "stripped the colon with no field before it",
            )
    return None


def repair(text: str) -> Repair:
    try:
        return Repair(query=parse(text), mends=())
    except QuarryError:
        pass
    mends: list[str] = []
    current = text
    for _ in range(MEND_CAP):
        step = _mend_once(current)
        if step is None:
            break
        current, mend = step
        mends.append(mend)
        try:
            return Repair(query=parse(current), mends=tuple(mends))
        except QuarryError:
            continue
    raise Invalid(
        f"{text!r} is beyond {MEND_CAP} mend(s); this is not a "
        f"query with typos, it is noise wearing a query's shape"
    )
