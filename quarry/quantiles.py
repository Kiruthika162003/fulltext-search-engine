"""Streaming quantiles: the p95 is estimated, and says by how much.

Latency dashboards need percentiles over streams too large to
sort, and the honest fix is a fixed set of buckets with declared
edges: each observation lands in a bucket, quantiles interpolate
inside the winning bucket, and the answer carries its error
bound, the bucket's own width, because an estimated p95 quoted
without its resolution reads as truth and is only a bucket. The
edges grow geometrically since latency pain is multiplicative,
the difference between 10 and 20 milliseconds matters like the
difference between 100 and 200 does, and observations beyond
the last edge count in an overflow bucket whose existence is
reported, never hidden, because the overflow filling up is
exactly the signal that the scale was built for a service that
no longer exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

EDGES = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)


@dataclass
class QuantileSketch:
    counts: list[int] = field(
        default_factory=lambda: [0] * (len(EDGES) + 1)
    )
    total: int = 0

    def observe(self, value: int) -> None:
        if value < 0:
            raise Invalid("negative latency is a clock bug")
        self.total += 1
        for index, edge in enumerate(EDGES):
            if value <= edge:
                self.counts[index] += 1
                return
        self.counts[-1] += 1

    def overflow(self) -> int:
        return self.counts[-1]

    def quantile(self, share: float) -> tuple[int, str]:
        if not 0.0 < share < 1.0:
            raise Invalid(
                "quantiles live strictly between 0 and 1; the ends "
                "are min and max, ask for those honestly"
            )
        if self.total == 0:
            raise Invalid("no observations; the quantile is fiction")
        target = share * self.total
        seen = 0
        for index, count in enumerate(self.counts):
            seen += count
            if seen >= target:
                if index == len(EDGES):
                    return EDGES[-1], (
                        f"BEYOND THE SCALE: p{share:.0%} sits in "
                        f"the overflow past {EDGES[-1]}"
                    )
                lower = EDGES[index - 1] if index > 0 else 0
                upper = EDGES[index]
                return upper, (
                    f"p{share:.0%} <= {upper} (resolution: the "
                    f"({lower}, {upper}] bucket)"
                )
        raise Invalid("unreachable: counts summed under total")

    def report(self) -> str:
        if self.total == 0:
            return "no observations yet"
        lines = []
        for share in (0.5, 0.95, 0.99):
            _, described = self.quantile(share)
            lines.append(described)
        if self.overflow():
            overflow_share = self.overflow() / self.total
            lines.append(
                f"OVERFLOW: {self.overflow()} observation(s) "
                f"({overflow_share:.1%}) past the last edge; the "
                f"scale was built for a service that no longer "
                f"exists"
            )
        lines.append(f"n={self.total}")
        return "\n".join(lines)


def merged(sketches: list[QuantileSketch]) -> QuantileSketch:
    """Shard sketches merge by adding buckets; that is the point."""
    if not sketches:
        raise Invalid("merging no sketches makes no sketch")
    out = QuantileSketch()
    for sketch in sketches:
        out.total += sketch.total
        for index, count in enumerate(sketch.counts):
            out.counts[index] += count
    return out
