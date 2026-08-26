"""Length normalisation earns its keep against a padded impostor.

Two documents mention the query term once: a twelve-word answer
and the same answer padded to ten times the length with filler
that mentions nothing. With b at its default, the short document
outranks the padded one, because one mention in a tweet is worth
more than one mention in a novel. With b forced to zero the two
scores collapse to a tie, the padding costless, and tying is
exactly how content farms win: pad the page, keep the mention,
ride the equal score. The eval pins both worlds so the default is
a measured defence, not an aesthetic, and pins the margin too,
since a defence that wins by a rounding error is a defence one
refactor from losing.
"""

from __future__ import annotations

from quarry.evals.grade import Grade
from quarry.scoring import TermStats, bm25_term

SHORT_LENGTH = 12
PADDED_LENGTH = 120
AVERAGE = (SHORT_LENGTH + PADDED_LENGTH) / 2


def run() -> Grade:
    stats = TermStats(term="answer", document_frequency=2, corpus_docs=2)
    defended_short = bm25_term(
        stats, 1, length=SHORT_LENGTH, average_length=AVERAGE
    )
    defended_padded = bm25_term(
        stats, 1, length=PADDED_LENGTH, average_length=AVERAGE
    )
    undefended_short = bm25_term(
        stats, 1, length=SHORT_LENGTH, average_length=AVERAGE, b=0.0
    )
    undefended_padded = bm25_term(
        stats, 1, length=PADDED_LENGTH, average_length=AVERAGE, b=0.0
    )
    margin = (
        (defended_short - defended_padded) / defended_padded
        if defended_padded
        else 0.0
    )
    numbers = {
        "defended_short": round(defended_short, 4),
        "defended_padded": round(defended_padded, 4),
        "undefended_tie": undefended_short == undefended_padded,
        "margin": round(margin, 2),
    }
    holds = (
        defended_short > defended_padded
        and numbers["undefended_tie"]
        and margin > 0.5
    )
    return Grade(
        eval_name="lengthnorm",
        sentence=(
            "with b on, the short answer beats its padded impostor by "
            "a wide margin; with b off they tie and the content farm "
            "rides the equal score"
        ),
        numbers=numbers,
        holds=holds,
    )
