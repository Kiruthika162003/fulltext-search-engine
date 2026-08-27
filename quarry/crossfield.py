"""Cross-field matching: best field wins, the rest whisper.

A query word can match the title, the body, or both, and adding
those scores lets a word that brushes five fields outrank one
that nails the field that matters. The dismax rule fixes the
inflation: per query term, the score is the BEST single field's
score plus a small tiebreaker times the others, so matching
many fields breaks ties but never beats matching the right
field well. The tiebreaker lives in [0, 1) and is declared at
construction, zero meaning pure winner-takes-all; a tiebreaker
of one would restore the summing bug wearing a parameter's
name, so it is refused. Per-field boosts multiply before the
max so an important field can win with a weaker raw match, and
the explain output shows the winner, the whispers, and the
arithmetic per term, because a combined score nobody can
decompose is a combined score nobody can debug.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid


@dataclass(frozen=True)
class FieldScore:
    field_name: str
    raw: float
    boost: float

    def weighted(self) -> float:
        return round(self.raw * self.boost, 6)


@dataclass(frozen=True)
class TermVerdict:
    term: str
    winner: FieldScore
    whispers: tuple[FieldScore, ...]
    tiebreak: float

    def score(self) -> float:
        whisper_sum = sum(
            held.weighted() for held in self.whispers
        )
        return round(
            self.winner.weighted() + self.tiebreak * whisper_sum, 6
        )

    def explain(self) -> str:
        parts = [
            f"{self.term}: {self.winner.field_name} wins at "
            f"{self.winner.weighted()}"
        ]
        if self.whispers:
            listed = ", ".join(
                f"{held.field_name}={held.weighted()}"
                for held in self.whispers
            )
            parts.append(
                f"whispers ({listed}) x tiebreak {self.tiebreak}"
            )
        parts.append(f"= {self.score()}")
        return " ".join(parts)


@dataclass
class CrossFieldScorer:
    boosts: dict[str, float]
    tiebreak: float = 0.1

    def __post_init__(self) -> None:
        if not self.boosts:
            raise Invalid("no fields to score across")
        if not 0.0 <= self.tiebreak < 1.0:
            raise Invalid(
                f"a tiebreaker of {self.tiebreak} restores the "
                f"summing bug wearing a parameter's name; it lives "
                f"in [0, 1)"
            )
        for name, boost in self.boosts.items():
            if boost <= 0:
                raise Invalid(
                    f"{name}: a boost of {boost} silences the "
                    f"field; drop it from the scorer instead"
                )

    def judge_term(
        self, term: str, raw_scores: dict[str, float]
    ) -> TermVerdict | None:
        strays = set(raw_scores) - set(self.boosts)
        if strays:
            raise Invalid(
                f"{term}: score(s) for unboosted field(s) "
                f"{', '.join(sorted(strays))}"
            )
        scored = [
            FieldScore(
                field_name=name,
                raw=raw,
                boost=self.boosts[name],
            )
            for name, raw in raw_scores.items()
            if raw > 0.0
        ]
        if not scored:
            return None
        scored.sort(
            key=lambda held: (-held.weighted(), held.field_name)
        )
        return TermVerdict(
            term=term,
            winner=scored[0],
            whispers=tuple(scored[1:]),
            tiebreak=self.tiebreak,
        )

    def score_document(
        self, per_term: dict[str, dict[str, float]]
    ) -> tuple[float, list[str]]:
        total = 0.0
        lines = []
        for term in sorted(per_term):
            verdict = self.judge_term(term, per_term[term])
            if verdict is None:
                lines.append(f"{term}: no field matched")
                continue
            total = round(total + verdict.score(), 6)
            lines.append(verdict.explain())
        return total, lines
