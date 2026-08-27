"""Document provenance: which feed, which batch, which hands.

When a wrong document surfaces, the first question is never
about ranking, it is where did this come from, and provenance
answers from the record: every document carries its source
feed, the batch that delivered it, the pipeline version that
processed it, and the chain of transformations applied, each
appended and never edited, because provenance that can be
rewritten is testimony, not evidence. The blame query works
both directions: a document answers with its full chain, and a
suspect batch answers with every document it delivered, the
recall list ready before anyone asks. Chains are append-only
by construction, a transformation with no name refuses since
anonymous edits are how mystery documents are born, and the
feed report aggregates by source so the feed that ships the
most corrections becomes visible as a number instead of a
feeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass
class ProvenanceLedger:
    origins: dict[int, tuple[str, str, str]] = field(
        default_factory=dict
    )
    chains: dict[int, list[str]] = field(default_factory=dict)

    def register(
        self,
        external: int,
        feed: str,
        batch: str,
        pipeline_version: str,
    ) -> str:
        if external in self.origins:
            raise Invalid(
                f"doc {external} already has an origin; a second "
                f"birth is a laundering, reindex under the chain"
            )
        for label, value in (
            ("feed", feed),
            ("batch", batch),
            ("pipeline", pipeline_version),
        ):
            if not value.strip():
                raise Invalid(
                    f"doc {external}: an empty {label} is an "
                    f"anonymous origin"
                )
        self.origins[external] = (feed, batch, pipeline_version)
        self.chains[external] = []
        return f"doc {external}: {feed}/{batch} via {pipeline_version}"

    def transform(
        self, external: int, step: str, who: str
    ) -> str:
        if external not in self.origins:
            raise Missing(
                f"doc {external} has no origin; transformations "
                f"on the unregistered are mystery documents being "
                f"born"
            )
        if not step.strip() or not who.strip():
            raise Invalid(
                "anonymous edits are how mystery documents are "
                "born; name the step and the hands"
            )
        self.chains[external].append(f"{step} by {who}")
        return f"doc {external}: +{step}"

    def blame(self, external: int) -> str:
        origin = self.origins.get(external)
        if origin is None:
            raise Missing(f"doc {external} has no provenance at all")
        feed, batch, pipeline = origin
        lines = [
            f"doc {external}: born of {feed}/{batch} via "
            f"{pipeline}"
        ]
        chain = self.chains[external]
        if chain:
            lines.extend(f"  then {step}" for step in chain)
        else:
            lines.append("  untouched since birth")
        return "\n".join(lines)

    def recall_list(self, batch: str) -> list[int]:
        found = sorted(
            external
            for external, (_, held_batch, _) in self.origins.items()
            if held_batch == batch
        )
        if not found:
            raise Missing(
                f"batch {batch!r} delivered nothing on record; "
                f"either the wrong name or the scarier answer"
            )
        return found

    def feed_report(self) -> str:
        if not self.origins:
            return "no documents on record"
        counts: dict[str, int] = {}
        touched: dict[str, int] = {}
        for external, (feed, _, _) in self.origins.items():
            counts[feed] = counts.get(feed, 0) + 1
            if self.chains[external]:
                touched[feed] = touched.get(feed, 0) + 1
        lines = []
        for feed in sorted(counts):
            corrections = touched.get(feed, 0)
            share = corrections / counts[feed]
            lines.append(
                f"{feed}: {counts[feed]} document(s), "
                f"{corrections} corrected ({share:.0%})"
            )
        return "\n".join(lines)
