"""Click reranking: clicks vote, but position gets to the booth first.

Raw click counts flatter whatever already ranked first, because
position one gets seen and position nine gets scrolled past; a
reranker that feeds on raw clicks builds a flywheel where the
incumbent wins for having won. The correction here divides each
result's clicks by its position's examination rate, the measured
probability that anyone looked at that position at all, turning
clicks into clicks-per-look. The blend is deliberate and bounded:
corrected click evidence adjusts the relevance score by at most
the blend weight, because behaviour should tune a ranking, not
replace it, and a document with great clicks for the wrong query
is one viral moment from owning a keyword it never mentions. Cold
documents with no impressions keep their pure relevance score
untouched rather than being averaged toward zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

EXAMINATION = (1.0, 0.85, 0.7, 0.55, 0.45, 0.35, 0.3, 0.25, 0.2, 0.18)
BLEND = 0.3


@dataclass
class ClickBook:
    impressions: dict[int, dict[int, int]] = field(default_factory=dict)
    clicks: dict[int, int] = field(default_factory=dict)

    def shown(self, external: int, position: int) -> None:
        if position < 0:
            raise Invalid("positions count from zero, downward only")
        held = self.impressions.setdefault(external, {})
        held[position] = held.get(position, 0) + 1

    def clicked(self, external: int) -> None:
        if external not in self.impressions:
            raise Invalid(
                f"a click on doc {external} that was never shown; the "
                f"instrumentation is lying"
            )
        self.clicks[external] = self.clicks.get(external, 0) + 1

    def expected_examinations(self, external: int) -> float:
        held = self.impressions.get(external, {})
        total = 0.0
        for position, count in held.items():
            rate = (
                EXAMINATION[position]
                if position < len(EXAMINATION)
                else EXAMINATION[-1]
            )
            total += rate * count
        return total

    def corrected_rate(self, external: int) -> float | None:
        """Clicks per look, or None for the never-shown."""
        examinations = self.expected_examinations(external)
        if examinations == 0.0:
            return None
        return round(
            self.clicks.get(external, 0) / examinations, 4
        )


@dataclass(frozen=True)
class RerankedHit:
    external: int
    base_score: float
    behaviour: float | None
    final: float


def rerank(
    ranked: list[tuple[int, float]],
    book: ClickBook,
    blend: float = BLEND,
) -> list[RerankedHit]:
    if not 0.0 <= blend < 1.0:
        raise Invalid(
            "the blend is a fraction under one; behaviour tunes a "
            "ranking, it does not replace it"
        )
    out = []
    for external, base in ranked:
        rate = book.corrected_rate(external)
        if rate is None:
            final = base
        else:
            final = base * (1.0 - blend) + base * blend * min(rate, 2.0)
        out.append(
            RerankedHit(
                external=external,
                base_score=base,
                behaviour=rate,
                final=round(final, 6),
            )
        )
    out.sort(key=lambda hit: (-hit.final, hit.external))
    return out


def flywheel_check(
    book: ClickBook, top_external: int, challenger_external: int
) -> str:
    """Compare corrected rates: does the incumbent win on merit."""
    top_rate = book.corrected_rate(top_external)
    challenger_rate = book.corrected_rate(challenger_external)
    if top_rate is None or challenger_rate is None:
        return "not enough evidence to judge the flywheel"
    if challenger_rate > top_rate:
        return (
            f"the challenger earns {challenger_rate} clicks-per-look "
            f"against the incumbent's {top_rate}; the raw counts were "
            f"the flywheel talking"
        )
    return (
        f"the incumbent holds on merit: {top_rate} against "
        f"{challenger_rate} clicks-per-look"
    )
