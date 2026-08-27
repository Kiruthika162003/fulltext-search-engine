"""Ship day: gates report, the board decides, the record survives.

Run with: python -m examples.shipday
"""

from __future__ import annotations

from quarry.canary import Canary
from quarry.evals.grade import Grade
from quarry.indexfreeze import FreezeBoard, FreezeWindow
from quarry.launchboard import LaunchBoard
from quarry.regressiongate import gate
from quarry.shadowindex import ShadowLedger


def run_gates() -> LaunchBoard:
    board = LaunchBoard(build="ranker-v12")

    before = [Grade(eval_name="rarewins", sentence="s", holds=True)]
    after = [Grade(eval_name="rarewins", sentence="s", holds=True)]
    verdict = gate(before, after)
    board.report_gate(
        "regression",
        verdict.ships,
        verdict.report().splitlines()[0],
    )

    shadow = ShadowLedger()
    for n in range(60):
        shadow.record_comparison(f"q{n}", [1, 2], [1, 2])
    ready, words = shadow.ready_to_cut()
    board.report_gate("shadow", ready, words)

    canary = Canary()
    for _ in range(50):
        canary.ledgers["canary"].observe(1)
        canary.ledgers["incumbent"].observe(1)
    verdict_line = canary.verdict()
    board.report_gate(
        "canary",
        verdict_line.startswith("SHIP"),
        verdict_line.split(":")[0],
    )

    freezes = FreezeBoard()
    freezes.declare(
        FreezeWindow(
            start=100,
            end=200,
            reason="peak weekend",
            owner="search-lead",
        )
    )
    words = freezes.check("reindex", tick=90)
    board.report_gate("freeze", "proceeds" in words, words)
    return board


def main() -> int:
    board = run_gates()
    print(board.page())
    return 0 if board.go() else 1


if __name__ == "__main__":
    raise SystemExit(main())
