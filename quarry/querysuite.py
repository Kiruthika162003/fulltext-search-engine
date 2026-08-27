"""Golden queries: the ranking's regression suite, diffed release by release.

Evals grade principles; golden queries guard specifics. A golden
entry is a query with its expected top results as of the day
somebody blessed them, and the suite's job on every release is to
say exactly what moved: same, reordered, or changed membership,
in escalating severity, because a reorder within the same five
documents is a tuning note while a new document in the top three
is a review. Blessing is explicit and journaled, who and when and
why, since a golden file updated silently is a regression suite
that approves its own regressions. The suite refuses to bless a
failing comparison in the same breath as reporting it, two calls
by design, because the person who sees the diff and the person
who accepts it should at least have to be the same person twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass(frozen=True)
class GoldenEntry:
    query: str
    expected: tuple[int, ...]
    blessed_by: str
    blessed_at: int
    note: str


@dataclass(frozen=True)
class Comparison:
    query: str
    verdict: str
    expected: tuple[int, ...]
    observed: tuple[int, ...]

    def severity(self) -> int:
        return {"same": 0, "reordered": 1, "changed": 2}[self.verdict]


@dataclass
class GoldenSuite:
    entries: dict[str, GoldenEntry] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)

    def bless(
        self,
        query: str,
        observed: tuple[int, ...],
        who: str,
        at: int,
        note: str,
    ) -> None:
        if not note.strip():
            raise Invalid(
                "a blessing without a note approves its own regressions"
            )
        if not observed:
            raise Invalid(
                f"{query!r}: blessing an empty result set enshrines a "
                f"broken query"
            )
        self.entries[query] = GoldenEntry(
            query=query,
            expected=observed,
            blessed_by=who,
            blessed_at=at,
            note=note,
        )
        self.journal.append(
            f"[{at}] {query!r} blessed by {who}: {note}"
        )

    def compare(
        self, query: str, observed: tuple[int, ...]
    ) -> Comparison:
        entry = self.entries.get(query)
        if entry is None:
            raise Missing(f"{query!r} was never blessed")
        if observed == entry.expected:
            verdict = "same"
        elif set(observed) == set(entry.expected):
            verdict = "reordered"
        else:
            verdict = "changed"
        return Comparison(
            query=query,
            verdict=verdict,
            expected=entry.expected,
            observed=observed,
        )

    def release_report(
        self, observations: dict[str, tuple[int, ...]]
    ) -> str:
        if not self.entries:
            raise Invalid("an empty suite guards nothing")
        rows = []
        for query in sorted(self.entries):
            observed = observations.get(query)
            if observed is None:
                rows.append(
                    Comparison(
                        query=query,
                        verdict="changed",
                        expected=self.entries[query].expected,
                        observed=(),
                    )
                )
                continue
            rows.append(self.compare(query, observed))
        rows.sort(key=lambda row: (-row.severity(), row.query))
        worst = rows[0].verdict if rows else "same"
        lines = [
            f"{len(rows)} golden quer(ies), worst verdict: {worst}"
        ]
        for row in rows:
            if row.verdict == "same":
                lines.append(f"  same: {row.query!r}")
            elif row.verdict == "reordered":
                lines.append(
                    f"  reordered: {row.query!r} "
                    f"{list(row.expected)} -> {list(row.observed)}"
                )
            else:
                lines.append(
                    f"  CHANGED: {row.query!r} "
                    f"{list(row.expected)} -> {list(row.observed)}; "
                    f"membership moved, this needs a review"
                )
        return "\n".join(lines)
