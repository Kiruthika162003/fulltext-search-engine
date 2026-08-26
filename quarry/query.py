"""The query language: what the user typed, parsed without guessing.

The grammar is small and closed: bare words rank, quoted words are
phrases, plus means must, minus means must-not, field:term aims a
clause at one field, and OR between clauses widens instead of
narrowing. Parsing never guesses: an unclosed quote is an error
carrying the position, an empty query is refused rather than
matching everything, and a query that is all exclusions is refused
because "not this" over an unbounded corpus is a question with no
answer. The parse result is a tree of typed clauses the searcher
walks, and printing the tree back gives a canonical form so two
queries that mean the same thing can be seen to mean the same
thing.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

DEFAULT_FIELD = "body"


@dataclass(frozen=True)
class Clause:
    kind: str
    field: str
    text: str
    required: bool = False
    prohibited: bool = False

    def canonical(self) -> str:
        mark = "+" if self.required else "-" if self.prohibited else ""
        body = f'"{self.text}"' if self.kind == "phrase" else self.text
        return f"{mark}{self.field}:{body}"


@dataclass(frozen=True)
class Query:
    groups: tuple[tuple[Clause, ...], ...]

    def canonical(self) -> str:
        return " OR ".join(
            " ".join(clause.canonical() for clause in group)
            for group in self.groups
        )


def _split_field(word: str, default_field: str) -> tuple[str, str]:
    if ":" in word:
        field_name, _, rest = word.partition(":")
        if not field_name or not rest:
            raise Invalid(
                f"a field clause needs both sides of the colon: {word!r}"
            )
        return field_name, rest
    return default_field, word


def _tokenize_query(text: str) -> list[str]:
    """Split on whitespace, except inside quotes, which bind tighter.

    A quote opening mid-piece extends the piece through its closing
    quote, so title:"deep work" stays one piece; an unclosed quote
    is an error carrying the position it opened at.
    """
    pieces: list[str] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        end = index
        while end < len(text) and not text[end].isspace():
            if text[end] == '"':
                closing = text.find('"', end + 1)
                if closing == -1:
                    raise Invalid(
                        f"unclosed quote starting at position {end}"
                    )
                end = closing + 1
            else:
                end += 1
        pieces.append(text[index:end])
        index = end
    return pieces


def parse(text: str, default_field: str = DEFAULT_FIELD) -> Query:
    if not text.strip():
        raise Invalid("an empty query is refused, not matched to everything")
    groups: list[list[Clause]] = [[]]
    for piece in _tokenize_query(text):
        if piece == "OR":
            if not groups[-1]:
                raise Invalid("OR needs a clause on both sides")
            groups.append([])
            continue
        required = piece.startswith("+")
        prohibited = piece.startswith("-")
        bare = piece[1:] if (required or prohibited) else piece
        if not bare:
            raise Invalid(f"a lone {piece!r} modifies nothing")
        if bare.startswith('"') or '"' in bare:
            field_name = default_field
            phrase_text = bare
            if not bare.startswith('"'):
                field_name, phrase_text = _split_field(bare, default_field)
            if not (
                phrase_text.startswith('"') and phrase_text.endswith('"')
            ):
                raise Invalid(f"a phrase must be fully quoted: {piece!r}")
            inner = phrase_text[1:-1]
            if not inner.strip():
                raise Invalid("an empty phrase matches nothing")
            groups[-1].append(
                Clause(
                    kind="phrase",
                    field=field_name,
                    text=inner,
                    required=required,
                    prohibited=prohibited,
                )
            )
            continue
        field_name, term_text = _split_field(bare, default_field)
        groups[-1].append(
            Clause(
                kind="term",
                field=field_name,
                text=term_text,
                required=required,
                prohibited=prohibited,
            )
        )
    if not groups[-1]:
        raise Invalid("OR needs a clause on both sides")
    for group in groups:
        if all(clause.prohibited for clause in group):
            raise Invalid(
                "a group of pure exclusions asks for everything except; "
                "add one positive clause to anchor it"
            )
    return Query(groups=tuple(tuple(group) for group in groups))
