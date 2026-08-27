"""A keyboard-aware typo model: fat fingers are not random noise.

Edit distance treats every substitution as equally likely, but
hands on a QWERTY keyboard disagree: q for w is a slip, q for p
is a different word. The model prices each edit by mechanism,
adjacent-key substitutions and doubled letters and transpositions
of neighbors are cheap because fingers actually do them, while
substitutions across the keyboard pay full price, and the total
cost of explaining one string as a typo of another is the sum of
its cheapest edit path priced this way. Candidate correction
uses the prices to rank: among dictionary words within budget,
the cheapest mechanical explanation wins, with frequency as the
tiebreaker, never the other way around, because a popular word
that requires an implausible slip is how autocorrect invents
messages people did not type.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")

CHEAP = 0.4
FULL = 1.0
BUDGET = 2.0


def _positions() -> dict[str, tuple[int, int]]:
    grid = {}
    for row_index, row in enumerate(ROWS):
        for col_index, char in enumerate(row):
            grid[char] = (row_index, col_index)
    return grid


KEY_AT = _positions()


def adjacent(left: str, right: str) -> bool:
    if left not in KEY_AT or right not in KEY_AT:
        return False
    left_row, left_col = KEY_AT[left]
    right_row, right_col = KEY_AT[right]
    return (
        abs(left_row - right_row) <= 1
        and abs(left_col - right_col) <= 1
        and left != right
    )


def substitution_price(left: str, right: str) -> float:
    return CHEAP if adjacent(left, right) else FULL


def typo_cost(typed: str, intended: str) -> float:
    """Cheapest mechanically-priced edit path, classic DP."""
    if not typed or not intended:
        raise Invalid("typo pricing needs both spellings")
    typed = typed.lower()
    intended = intended.lower()
    rows = len(typed) + 1
    cols = len(intended) + 1
    table = [[0.0] * cols for _ in range(rows)]
    for i in range(1, rows):
        table[i][0] = i * FULL
    for j in range(1, cols):
        table[0][j] = j * FULL
    for i in range(1, rows):
        for j in range(1, cols):
            if typed[i - 1] == intended[j - 1]:
                substitute = table[i - 1][j - 1]
            else:
                substitute = table[i - 1][j - 1] + substitution_price(
                    typed[i - 1], intended[j - 1]
                )
            delete_price = (
                CHEAP
                if i >= 2 and typed[i - 1] == typed[i - 2]
                else FULL
            )
            delete = table[i - 1][j] + delete_price
            insert = table[i][j - 1] + FULL
            best = min(substitute, delete, insert)
            if (
                i >= 2
                and j >= 2
                and typed[i - 1] == intended[j - 2]
                and typed[i - 2] == intended[j - 1]
            ):
                swap_price = (
                    CHEAP
                    if adjacent(typed[i - 2], typed[i - 1])
                    else FULL
                )
                best = min(best, table[i - 2][j - 2] + swap_price)
            table[i][j] = best
    return round(table[-1][-1], 4)


@dataclass(frozen=True)
class Correction:
    word: str
    cost: float
    frequency: int

    def line(self) -> str:
        return (
            f"{self.word} (slip cost {self.cost}, seen "
            f"{self.frequency}x)"
        )


def correct(
    typed: str, dictionary: dict[str, int]
) -> list[Correction]:
    if not dictionary:
        raise Invalid("correcting against an empty dictionary")
    candidates = []
    for word, frequency in dictionary.items():
        if abs(len(word) - len(typed)) > 2:
            continue
        cost = typo_cost(typed, word)
        if cost == 0.0 or cost > BUDGET:
            continue
        candidates.append(
            Correction(word=word, cost=cost, frequency=frequency)
        )
    candidates.sort(
        key=lambda held: (held.cost, -held.frequency, held.word)
    )
    return candidates
