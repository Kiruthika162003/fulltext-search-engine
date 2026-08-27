"""The launch board: every gate's verdict on one page, or no launch.

Shipping a ranking change crosses four gates that live in four
tools: the regression gate over the evals, the shadow ledger's
cutover bar, the canary's arm comparison, and the freeze
calendar. The board is where they meet: each gate reports
green or red with its own words quoted, the launch verdict is
the conjunction because three greens and a red is a red, and a
gate that has not reported is a red that says not reported
rather than an absence someone optimistic reads as passed. The
board is assembled fresh per launch, never carried over,
because yesterday's greens describe yesterday's build, and the
one-page render is the artifact that goes in the launch
thread, so the decision and its evidence travel together and
the retro reads the same page the decision did.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

GATES = ("regression", "shadow", "canary", "freeze")


@dataclass(frozen=True)
class GateVerdict:
    gate: str
    green: bool
    words: str

    def line(self) -> str:
        mark = "GREEN" if self.green else "RED"
        return f"[{mark}] {self.gate}: {self.words}"


@dataclass
class LaunchBoard:
    build: str
    verdicts: dict[str, GateVerdict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.build.strip():
            raise Invalid(
                "a launch board without a build launches nothing "
                "in particular, which is how wrong builds ship"
            )

    def report_gate(
        self, gate: str, green: bool, words: str
    ) -> str:
        if gate not in GATES:
            raise Missing(
                f"{gate!r} is not a launch gate; the gates are "
                f"{', '.join(GATES)}"
            )
        if not words.strip():
            raise Invalid(
                f"{gate}: a verdict without words cannot be "
                f"argued with, which is the problem"
            )
        if gate in self.verdicts:
            raise Invalid(
                f"{gate} already reported for {self.build}; a "
                f"second opinion goes on a fresh board"
            )
        self.verdicts[gate] = GateVerdict(
            gate=gate, green=green, words=words
        )
        return f"{gate} reported for {self.build}"

    def unreported(self) -> list[str]:
        return [
            gate for gate in GATES if gate not in self.verdicts
        ]

    def go(self) -> bool:
        return not self.unreported() and all(
            held.green for held in self.verdicts.values()
        )

    def page(self) -> str:
        lines = [f"launch board for {self.build}:"]
        for gate in GATES:
            held = self.verdicts.get(gate)
            if held is None:
                lines.append(
                    f"[RED] {gate}: not reported; silence is not "
                    f"a pass"
                )
            else:
                lines.append(held.line())
        if self.go():
            lines.append("VERDICT: GO, all four gates green")
        else:
            reds = [
                gate
                for gate in GATES
                if gate not in self.verdicts
                or not self.verdicts[gate].green
            ]
            lines.append(
                f"VERDICT: NO GO ({', '.join(reds)} red)"
            )
        return "\n".join(lines)
