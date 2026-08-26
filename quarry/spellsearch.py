"""Two-pass search: try what they typed, then try what they meant.

The first pass runs the query exactly as written, because the user
who typed an unusual word on purpose outranks every model of what
users usually mean. Only when the first pass comes back under the
rescue floor does the second pass run, with each unknown term
replaced by its best correction, and the response then carries
three things inseparably: the results, the corrected query that
produced them, and the phrase "showing results for", because
serving corrected results as if they were literal matches teaches
users the engine cannot be trusted at exactly the moment it was
being clever. When even the corrected pass finds nothing, the
answer is an honest empty page with the correction offered as a
link, never an auto-rerun spiral.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.engine import Engine, Response
from quarry.errors import Invalid
from quarry.fuzzy import did_you_mean

RESCUE_FLOOR = 1


@dataclass(frozen=True)
class SpellcheckedResponse:
    literal: Response
    served: Response
    corrected_from: str | None

    def banner(self) -> str | None:
        if self.corrected_from is None:
            return None
        return (
            f"showing results for {self.served.query!r} "
            f"(searched instead of {self.corrected_from!r})"
        )


def _correct_terms(engine: Engine, text: str) -> str | None:
    corrected = []
    changed = False
    for word in text.split():
        prefix = ""
        bare = word
        if ":" in bare:
            prefix, _, bare = bare.partition(":")
            prefix += ":"
        if bare.startswith(('"', "+", "-")) or not bare:
            corrected.append(word)
            continue
        declared = engine.schema.get(prefix[:-1] if prefix else "body")
        if declared.kind != "text":
            corrected.append(word)
            continue
        terms = declared.analyzer.terms(bare)
        if len(terms) != 1:
            corrected.append(word)
            continue
        offered = did_you_mean(engine.vocabulary, terms[0])
        if offered is None:
            corrected.append(word)
        else:
            corrected.append(f"{prefix}{offered}")
            changed = True
    if not changed:
        return None
    return " ".join(corrected)


def spellchecked_search(
    engine: Engine,
    text: str,
    limit: int = 10,
    rescue_floor: int = RESCUE_FLOOR,
) -> SpellcheckedResponse:
    if rescue_floor < 1:
        raise Invalid(
            "a rescue floor under one rescues pages that did not drown"
        )
    literal = engine.search(text, limit=limit)
    if len(literal.hits) >= rescue_floor:
        return SpellcheckedResponse(
            literal=literal, served=literal, corrected_from=None
        )
    corrected_text = _correct_terms(engine, text)
    if corrected_text is None:
        return SpellcheckedResponse(
            literal=literal, served=literal, corrected_from=None
        )
    corrected = engine.search(corrected_text, limit=limit)
    if not corrected.hits:
        return SpellcheckedResponse(
            literal=literal, served=literal, corrected_from=None
        )
    return SpellcheckedResponse(
        literal=literal, served=corrected, corrected_from=text
    )
