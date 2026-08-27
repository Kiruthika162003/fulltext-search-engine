"""Language sniffing: the stopwords give the language away.

Function words are the most frequent words in every language and
almost never borrowed, so a short text's language announces itself
by which stopword list it keeps hitting. The sniffer scores each
registered language by the share of tokens found in its function
word list, answers with the winner and the margin, and refuses to
guess when the margin is thin or the text too short, because a
sniffer that always answers is a sniffer that confidently labels
product codes as Estonian. The honest limits are in the docstring
on purpose: this distinguishes languages with distinct function
words and cannot tell dialects apart, which is most of what a
search engine needs, routing text to the right analyzer, and none
of what a linguist would ask.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

MINIMUM_TOKENS = 4
MINIMUM_MARGIN = 0.1

FUNCTION_WORDS = {
    "english": frozenset(
        "the a an and of to in is it that was for on are with he "
        "as at by this have from or had not but what all were "
        "when we there can".split()
    ),
    "german": frozenset(
        "der die das und ist ein eine zu den von mit nicht sich "
        "auf als auch es an werden aus er hat dass sie nach wird "
        "bei einer um am".split()
    ),
    "french": frozenset(
        "le la les de des un une et est dans que qui pour sur pas "
        "plus par avec ce se ne au du elle il nous vous ils sont "
        "mais ou si".split()
    ),
}


@dataclass(frozen=True)
class Sniff:
    language: str | None
    scores: tuple[tuple[str, float], ...]
    reason: str

    def confident(self) -> bool:
        return self.language is not None


@dataclass
class LanguageSniffer:
    vocabularies: dict[str, frozenset[str]] = field(
        default_factory=lambda: dict(FUNCTION_WORDS)
    )

    def register(self, language: str, words: frozenset[str]) -> None:
        if language in self.vocabularies:
            raise Invalid(f"{language} is already registered")
        if len(words) < 10:
            raise Invalid(
                f"{language}: a function word list under ten words "
                f"cannot carry a verdict"
            )
        self.vocabularies[language] = words

    def sniff(self, text: str) -> Sniff:
        tokens = [
            piece.lower()
            for piece in text.split()
            if piece.strip()
        ]
        if len(tokens) < MINIMUM_TOKENS:
            return Sniff(
                language=None,
                scores=(),
                reason=(
                    f"{len(tokens)} token(s) is too short to carry a "
                    f"verdict"
                ),
            )
        scored = []
        for language, words in self.vocabularies.items():
            hits = sum(1 for token in tokens if token in words)
            scored.append((language, round(hits / len(tokens), 4)))
        scored.sort(key=lambda row: (-row[1], row[0]))
        best_language, best_share = scored[0]
        runner_share = scored[1][1] if len(scored) > 1 else 0.0
        if best_share == 0.0:
            return Sniff(
                language=None,
                scores=tuple(scored),
                reason=(
                    "no function words hit any list; likely codes, "
                    "names, or a language nobody registered"
                ),
            )
        if best_share - runner_share < MINIMUM_MARGIN:
            return Sniff(
                language=None,
                scores=tuple(scored),
                reason=(
                    f"the margin between {best_language} and the "
                    f"runner-up is too thin to call"
                ),
            )
        return Sniff(
            language=best_language,
            scores=tuple(scored),
            reason=f"{best_share:.0%} of tokens are {best_language} "
            f"function words",
        )
