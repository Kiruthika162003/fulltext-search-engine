"""Click attribution that knows position one gets clicked for free.

Raw click counts flatter whatever already ranks first: position
one is seen by everyone and clicked out of habit, so counting
clicks without correcting for position teaches the ranker that
its old opinions were right. The examination model here is the
standard first cut: each position has an examination rate,
measured or assumed to decay, and a click's evidence of actual
relevance is the click divided by the odds anyone looked. A
skipped result above a clicked one is negative evidence with a
weight, not silence, because the user demonstrably examined and
declined it. The output is an attraction estimate per document
per query with the sample size beside it, and estimates from
single sightings are flagged rather than trusted, since one
click is an anecdote wearing a decimal point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

EXAMINATION = (1.0, 0.7, 0.5, 0.35, 0.25)
SMALL_SAMPLE = 3


def examination_rate(position: int) -> float:
    if position < 1:
        raise Invalid("positions start at one; zero is nowhere")
    if position <= len(EXAMINATION):
        return EXAMINATION[position - 1]
    return EXAMINATION[-1] / (position - len(EXAMINATION) + 1)


@dataclass
class Attraction:
    credit: float = 0.0
    weight: float = 0.0

    def estimate(self) -> float:
        if self.weight == 0.0:
            return 0.0
        return round(self.credit / self.weight, 4)


@dataclass
class ClickModel:
    table: dict[tuple[str, int], Attraction] = field(
        default_factory=dict
    )
    impressions_seen: int = 0

    def observe(
        self, canonical: str, shown: list[int], clicked: set[int]
    ) -> None:
        if not shown:
            raise Invalid(
                "an impression with no results teaches nothing"
            )
        stray = clicked - set(shown)
        if stray:
            listed = ", ".join(str(doc) for doc in sorted(stray))
            raise Invalid(
                f"click(s) on document(s) {listed} that were never "
                f"shown; the log is spliced from two impressions"
            )
        self.impressions_seen += 1
        deepest_click = max(
            (
                position
                for position, doc in enumerate(shown, start=1)
                if doc in clicked
            ),
            default=0,
        )
        for position, doc in enumerate(shown, start=1):
            held = self.table.setdefault(
                (canonical, doc), Attraction()
            )
            rate = examination_rate(position)
            if doc in clicked:
                held.credit += 1.0
                held.weight += rate
            elif position < deepest_click:
                held.weight += rate

    def attraction(self, canonical: str, doc: int) -> float:
        held = self.table.get((canonical, doc))
        if held is None:
            return 0.0
        return min(held.estimate(), 1.0)

    def confident(self, canonical: str, doc: int) -> bool:
        held = self.table.get((canonical, doc))
        return held is not None and held.weight >= SMALL_SAMPLE

    def report(self, canonical: str) -> str:
        rows = [
            (doc, held)
            for (query, doc), held in self.table.items()
            if query == canonical and held.weight > 0
        ]
        if not rows:
            return f"no evidence yet for {canonical!r}"
        rows.sort(key=lambda pair: (-pair[1].estimate(), pair[0]))
        lines = []
        for doc, held in rows:
            mark = (
                ""
                if held.weight >= SMALL_SAMPLE
                else " [thin evidence]"
            )
            lines.append(
                f"doc {doc}: attraction "
                f"{min(held.estimate(), 1.0)} from weight "
                f"{round(held.weight, 2)}{mark}"
            )
        return "\n".join(lines)
