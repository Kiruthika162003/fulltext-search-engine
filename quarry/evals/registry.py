"""Every eval, one call, one report card."""

from __future__ import annotations

import importlib

from quarry.evals.grade import Grade

EVALS = (
    "quarry.evals.rarewins",
    "quarry.evals.phrasetruth",
    "quarry.evals.stemtrade",
    "quarry.evals.lengthnorm",
    "quarry.evals.twinties",
    "quarry.evals.synonymgain",
    "quarry.evals.proximitygain",
    "quarry.evals.collapsefair",
    "quarry.evals.foldgain",
    "quarry.evals.deadlinehonesty",
    "quarry.evals.costtruth",
)


def all_grades() -> list[Grade]:
    return [
        importlib.import_module(dotted).run() for dotted in EVALS
    ]


def broken() -> list[str]:
    return [grade.eval_name for grade in all_grades() if not grade.holds]


def report() -> str:
    grades = all_grades()
    lines = [grade.line() for grade in grades]
    failing = sum(1 for grade in grades if not grade.holds)
    lines.append(f"\n{len(grades)} evals, {failing} broken")
    return "\n".join(lines)
