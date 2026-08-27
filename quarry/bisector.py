"""Regression bisection: the breaking change found in log-two steps.

Search quality broke sometime in the last forty builds and
nobody noticed until today; reading forty diffs is a week,
bisecting is five probes. The bisector runs the classic binary
search over an ordered history using a verdict function, good
or bad, with the discipline the classic requires: the endpoints
are probed first because a bisection whose first assumption is
wrong hunts a phantom, every probe is journaled with its
verdict so the hunt is auditable, and a flaky verdict, one
that answers differently for the same build, is detected by
the endpoint recheck and aborts the hunt loudly, since
bisecting on a coin flip converges confidently on an innocent
build. The answer names the first bad build and its
predecessor, the pair the diff reader actually wants, and the
probe count ships beside it as the receipt for why bisection
beats reading.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass
class Bisection:
    builds: list[str]
    verdict: Callable[[str], bool]
    journal: list[str] = field(default_factory=list)
    probes: int = 0

    def _probe(self, index: int) -> bool:
        build = self.builds[index]
        good = self.verdict(build)
        self.probes += 1
        self.journal.append(
            f"probe {self.probes}: {build} is "
            f"{'good' if good else 'BAD'}"
        )
        return good

    def hunt(self) -> str:
        if len(self.builds) < 2:
            raise Invalid(
                "bisecting fewer than two builds is just looking "
                "at a build"
            )
        first_good = self._probe(0)
        if not first_good:
            raise Invalid(
                f"the oldest build {self.builds[0]} is already "
                f"bad; the regression predates this history, "
                f"widen the range"
            )
        last_bad = self._probe(len(self.builds) - 1)
        if last_bad:
            raise Invalid(
                f"the newest build {self.builds[-1]} is good; "
                f"there is no regression in this range to hunt"
            )
        if self.verdict(self.builds[0]) != first_good:
            raise Invalid(
                "the verdict flipped on a recheck of the same "
                "build; bisecting on a coin flip convicts an "
                "innocent build. Stabilize the verdict first"
            )
        low = 0
        high = len(self.builds) - 1
        while high - low > 1:
            middle = (low + high) // 2
            if self._probe(middle):
                low = middle
            else:
                high = middle
        return (
            f"first bad: {self.builds[high]} (predecessor "
            f"{self.builds[low]}); {self.probes} probe(s) against "
            f"{len(self.builds)} builds"
        )

    def transcript(self) -> str:
        if not self.journal:
            return "no probes yet"
        return "\n".join(self.journal)
