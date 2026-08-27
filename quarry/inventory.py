"""The module inventory: the package describes itself, verifiably.

A codebase this wide needs a map that cannot rot, and the only
map that cannot rot is one generated from the code: the
inventory walks the package directory, reads each module's
docstring headline, the first line, which every module here
writes as a one-sentence thesis, and renders the catalog
grouped by prefix-free name order. Modules without a docstring
are listed under MISSING THESIS rather than skipped, because a
map that omits the unmapped parts pretends completeness it
does not have, and the count line at the bottom states modules
found and theses missing so a build gate can pin both numbers
and fail the day someone lands an undescribed module. The
inventory reads files, never imports them, since a catalog
that imports the world to describe it takes the world's import
time and the world's import bugs.
"""

from __future__ import annotations

import pathlib

from quarry.errors import Invalid


def _headline(source: str) -> str | None:
    stripped = source.lstrip()
    for quote in ('"""', "'''"):
        if stripped.startswith(quote):
            body = stripped[len(quote) :]
            first_line = body.splitlines()[0].strip()
            return first_line.rstrip(quote).strip() or None
    return None


def read_theses(package_dir: str) -> dict[str, str | None]:
    root = pathlib.Path(package_dir)
    if not root.is_dir():
        raise Invalid(f"{package_dir} is not a directory")
    found: dict[str, str | None] = {}
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("__"):
            continue
        source = path.read_text(encoding="utf-8")
        found[path.stem] = _headline(source)
    if not found:
        raise Invalid(
            f"{package_dir} holds no modules; the inventory of "
            f"nothing is nothing"
        )
    return found


def catalog(package_dir: str) -> str:
    theses = read_theses(package_dir)
    described = {
        name: thesis
        for name, thesis in theses.items()
        if thesis is not None
    }
    missing = sorted(
        name for name, thesis in theses.items() if thesis is None
    )
    lines = []
    for name in sorted(described):
        lines.append(f"{name}: {described[name]}")
    if missing:
        lines.append("MISSING THESIS:")
        lines.extend(f"  {name}" for name in missing)
    lines.append(
        f"{len(theses)} module(s), {len(missing)} without a thesis"
    )
    return "\n".join(lines)


def gate(package_dir: str) -> str:
    theses = read_theses(package_dir)
    missing = sorted(
        name for name, thesis in theses.items() if thesis is None
    )
    if missing:
        raise Invalid(
            f"module(s) {', '.join(missing)} have no docstring "
            f"headline; a module that cannot say its thesis in "
            f"one line does not know it yet"
        )
    return f"all {len(theses)} modules state their thesis"
