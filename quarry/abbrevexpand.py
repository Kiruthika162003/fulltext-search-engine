"""Abbreviation expansion: acronyms unfold, ambiguity refuses.

Corpora full of jargon index NDA and API and QPS while users
type the long forms and vice versa, so the book maps each
abbreviation to its expansion and searches match both ways.
The rule that keeps this from becoming a liability is the
ambiguity refusal: an abbreviation claimed by two expansions,
PM as product manager and as post meridiem, is marked contested
and expands to neither, because guessing wrong silently is
worse than not expanding, and the contested list is the
curator's worklist, resolvable only by choosing one expansion
per corpus, never both. Expansions are validated against their
abbreviation, first letters must match in order, since a book
where DB expands to structured query language has stopped
being an abbreviation book and become a synonym file with
delusions, and synonyms already have their own module with its
own discount arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


def _initials_match(abbrev: str, expansion: str) -> bool:
    words = [word for word in expansion.lower().split() if word]
    letters = [word[0] for word in words]
    return list(abbrev.lower()) == letters


@dataclass
class AbbrevBook:
    expansions: dict[str, str] = field(default_factory=dict)
    contested: dict[str, list[str]] = field(default_factory=dict)

    def declare(self, abbrev: str, expansion: str) -> str:
        cleaned = abbrev.strip().lower()
        spelled = expansion.strip().lower()
        if not cleaned or not spelled:
            raise Invalid("both sides of an abbreviation must exist")
        if not _initials_match(cleaned, spelled):
            raise Invalid(
                f"{cleaned!r} is not the initials of {spelled!r}; "
                f"that is a synonym with delusions, and synonyms "
                f"have their own module"
            )
        if cleaned in self.contested:
            self.contested[cleaned].append(spelled)
            return (
                f"{cleaned} is contested; added {spelled!r} to "
                f"the curator's worklist"
            )
        standing = self.expansions.get(cleaned)
        if standing is not None and standing != spelled:
            self.contested[cleaned] = [standing, spelled]
            del self.expansions[cleaned]
            return (
                f"{cleaned} is now CONTESTED between "
                f"{standing!r} and {spelled!r}; it expands to "
                f"neither until a curator chooses"
            )
        self.expansions[cleaned] = spelled
        return f"{cleaned} -> {spelled}"

    def resolve(self, abbrev: str, chosen: str) -> str:
        cleaned = abbrev.strip().lower()
        claims = self.contested.get(cleaned)
        if claims is None:
            raise Missing(
                f"{cleaned} is not contested; resolution is for "
                f"disputes"
            )
        if chosen.strip().lower() not in claims:
            raise Invalid(
                f"{chosen!r} was never a claim on {cleaned}; the "
                f"claims are {', '.join(claims)}"
            )
        self.expansions[cleaned] = chosen.strip().lower()
        del self.contested[cleaned]
        return f"{cleaned} resolved to {chosen.strip().lower()!r}"

    def expand_term(self, term: str) -> list[str]:
        cleaned = term.strip().lower()
        out = [cleaned]
        held = self.expansions.get(cleaned)
        if held is not None:
            out.extend(held.split())
        return out

    def abbreviate_phrase(self, phrase: str) -> str | None:
        spelled = phrase.strip().lower()
        for abbrev, expansion in self.expansions.items():
            if expansion == spelled:
                return abbrev
        return None

    def worklist(self) -> str:
        if not self.contested:
            return "nothing contested; the book is decisive"
        lines = ["contested abbreviations, expanding to neither:"]
        for abbrev in sorted(self.contested):
            claims = " vs ".join(
                repr(claim) for claim in self.contested[abbrev]
            )
            lines.append(f"  {abbrev}: {claims}")
        return "\n".join(lines)
