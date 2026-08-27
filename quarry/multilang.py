"""Per-language analyzer registry: one field, one language, no blend.

A catalog that serves three markets needs three analyzers, and
the classic wreck is one index where German and English share a
field: the stemmer mangles one language to serve the other and
recall dies quietly in whichever market the developers do not
read. The registry maps a language tag to its analyzer recipe,
stopwords and stemming declared per language, refuses lookups
for tags nobody registered rather than falling back silently,
because a silent fallback to English is exactly the wreck with
extra steps, and stamps every analysis with the tag it used so
an index can verify documents and queries agree on language
before they agree on anything else. Tags follow the primary
subtag convention, lowercase two or three letters, and region
variants are aliases declared on purpose, en-GB to en, never
guessed from the text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.tokenize import STOPWORDS, Analyzer

GERMAN_STOPWORDS = frozenset(
    "der die das und oder ein eine mit von zu im am".split()
)
FRENCH_STOPWORDS = frozenset(
    "le la les des un une et ou avec de du au aux".split()
)


@dataclass(frozen=True)
class LanguagePack:
    tag: str
    stopwords: frozenset[str]
    stems: bool

    def analyze(self, text: str) -> list[str]:
        base = Analyzer(
            drop_stopwords=False, stemming=self.stems
        ).terms(text)
        return [
            term for term in base if term not in self.stopwords
        ]


def _valid_tag(tag: str) -> bool:
    return tag.isascii() and tag.islower() and 2 <= len(tag) <= 3


@dataclass
class LanguageRegistry:
    packs: dict[str, LanguagePack] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)

    def register(self, pack: LanguagePack) -> None:
        if not _valid_tag(pack.tag):
            raise Invalid(
                f"{pack.tag!r} is not a primary subtag; lowercase "
                f"two or three letters"
            )
        if pack.tag in self.packs:
            raise Invalid(
                f"{pack.tag} is already registered; languages do "
                f"not get quietly replaced"
            )
        self.packs[pack.tag] = pack

    def alias(self, variant: str, target: str) -> None:
        if target not in self.packs:
            raise Missing(
                f"alias target {target} is not registered; declare "
                f"the language before its variants"
            )
        self.aliases[variant.lower()] = target

    def pack_for(self, tag: str) -> LanguagePack:
        lowered = tag.lower()
        resolved = self.aliases.get(lowered, lowered)
        held = self.packs.get(resolved)
        if held is None:
            registered = ", ".join(sorted(self.packs)) or "none"
            raise Missing(
                f"no analyzer registered for {tag!r} and silent "
                f"fallback is the wreck with extra steps; "
                f"registered: {registered}"
            )
        return held

    def analyze(self, tag: str, text: str) -> tuple[str, list[str]]:
        held = self.pack_for(tag)
        return held.tag, held.analyze(text)

    def agreement_check(
        self, document_tag: str, query_tag: str
    ) -> str:
        doc_pack = self.pack_for(document_tag)
        query_pack = self.pack_for(query_tag)
        if doc_pack.tag != query_pack.tag:
            raise Invalid(
                f"the index analyzed with {doc_pack.tag} and the "
                f"query with {query_pack.tag}; they must agree on "
                f"language before they agree on anything else"
            )
        return f"both sides speak {doc_pack.tag}"


def standard_registry() -> LanguageRegistry:
    registry = LanguageRegistry()
    registry.register(
        LanguagePack(tag="en", stopwords=STOPWORDS, stems=True)
    )
    registry.register(
        LanguagePack(
            tag="de", stopwords=GERMAN_STOPWORDS, stems=False
        )
    )
    registry.register(
        LanguagePack(
            tag="fr", stopwords=FRENCH_STOPWORDS, stems=False
        )
    )
    registry.alias("en-gb", "en")
    registry.alias("en-us", "en")
    registry.alias("de-at", "de")
    return registry
