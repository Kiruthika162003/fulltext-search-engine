"""Seasonality: last December predicts this one, if anyone kept it.

Query traffic has rhythms, umbrella spikes in monsoon and tax
software in April, and a trending detector without a seasonal
memory pages someone every year for the same December. The
ledger keeps per-term counts bucketed by period of year, and
the seasonal expectation for a period is the average of that
same period across kept years, so a spike is only a spike when
it beats what this season always does by the declared
multiple. Terms with no history are exempt from seasonal
judgment and fall back to plain trending, first appearances
being genuinely new information, and the ledger states how
many years back its memory runs, because an expectation from
one prior year is one anecdote and the report should say so
rather than dress it as climatology.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

SPIKE_MULTIPLE = 2.0
PERIODS_PER_YEAR = 12


@dataclass
class SeasonLedger:
    counts: dict[tuple[str, int, int], int] = field(
        default_factory=dict
    )

    def observe(
        self, term: str, year: int, period: int, count: int
    ) -> None:
        if not 1 <= period <= PERIODS_PER_YEAR:
            raise Invalid(
                f"period {period} is off the calendar; periods run "
                f"1 to {PERIODS_PER_YEAR}"
            )
        if count < 0:
            raise Invalid("negative counts are counting bugs")
        key = (term, year, period)
        if key in self.counts:
            raise Invalid(
                f"{term} in {year}-{period:02d} was already "
                f"recorded; periods close once"
            )
        self.counts[key] = count

    def history(self, term: str, period: int) -> list[int]:
        return [
            count
            for (held, year, held_period), count in sorted(
                self.counts.items()
            )
            if held == term and held_period == period
        ]

    def expectation(
        self, term: str, period: int, this_year: int
    ) -> tuple[float, int] | None:
        past = [
            count
            for (held, year, held_period), count in self.counts.items()
            if held == term
            and held_period == period
            and year < this_year
        ]
        if not past:
            return None
        return sum(past) / len(past), len(past)

    def judge(
        self, term: str, year: int, period: int, count: int
    ) -> str:
        held = self.expectation(term, period, year)
        if held is None:
            return (
                f"{term}: no seasonal memory for period {period}; "
                f"judge with plain trending, first appearances are "
                f"real information"
            )
        expected, years = held
        confidence = (
            "one prior year is an anecdote, not climatology"
            if years == 1
            else f"{years} years of memory"
        )
        if expected == 0:
            if count > 0:
                return (
                    f"{term}: {count} against a silent history "
                    f"({confidence}); genuinely new"
                )
            return f"{term}: silent, as this season always is"
        ratio = count / expected
        if ratio > SPIKE_MULTIPLE:
            return (
                f"{term}: SPIKE, {count} vs seasonal {expected:.0f} "
                f"({ratio:.1f}x, {confidence})"
            )
        return (
            f"{term}: seasonal, {count} vs expected {expected:.0f} "
            f"({confidence}); this is what this season does"
        )

    def memory_depth(self, term: str) -> str:
        years = {
            year
            for (held, year, _), _ in self.counts.items()
            if held == term
        }
        if not years:
            return f"{term}: no memory at all"
        span = max(years) - min(years) + 1
        return (
            f"{term}: memory spans {span} year(s), "
            f"{min(years)} to {max(years)}"
        )
