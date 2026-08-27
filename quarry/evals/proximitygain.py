"""Proximity separates the discussion from the coincidence, measured.

Two documents contain both query words: in one they sit adjacent,
an actual noun phrase; in the other they are twelve words apart,
strangers at the same party. Two lessons arrived while writing it. The first draft's
"twelve words apart" shrank to a slack of six after stopword
removal and earned a quarter bonus, so distance in prose is not
distance in positions and the fixture had to earn its zero. And
bag-of-words is not quite blind here: length normalisation already
nudges the shorter document up by 0.09, a lean, not a verdict.
The span bonus turns the lean into a margin of 1.09, full bonus
for adjacency against zero past the horizon, and the pinned pair,
the small before-gap and the full after-margin, is the argument
for shipping span scoring at all.
"""

from __future__ import annotations

from quarry.evals.grade import Grade
from quarry.proximity import proximity_bonus, span_windows
from quarry.schema import Schema
from quarry.scoring import TermStats, bm25_term
from quarry.segment import Segment, SegmentBuilder


def _library() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add(
        {
            "body": (
                "the climate summit opened with a policy debate "
                "and a long agenda"
            )
        }
    )
    builder.add(
        {
            "body": (
                "the climate report and eleven other papers on trade "
                "fisheries energy transport housing were filed before "
                "the summit"
            )
        }
    )
    return builder.seal("papers")


def run() -> Grade:
    segment = _library()
    terms = ["climate", "summit"]
    stats = {
        term: TermStats(
            term=term,
            document_frequency=2,
            corpus_docs=2,
        )
        for term in terms
    }
    base_scores = {}
    for doc in (0, 1):
        score = 0.0
        for term in terms:
            posting = segment.postings_for("body", term).find(doc)
            score += bm25_term(
                stats[term],
                posting.frequency,
                length=segment.field_length("body", doc),
                average_length=segment.average_field_length("body"),
            )
        base_scores[doc] = round(score, 6)
    base_gap = abs(base_scores[0] - base_scores[1])
    windows = {
        window.doc: window
        for window in span_windows(segment, "body", terms)
    }
    bonuses = {
        doc: proximity_bonus(
            windows[doc].width(), term_count=2
        )
        for doc in (0, 1)
    }
    final = {
        doc: round(base_scores[doc] + bonuses[doc], 6)
        for doc in (0, 1)
    }
    margin = round(final[0] - final[1], 6)
    numbers = {
        "base_gap": round(base_gap, 6),
        "adjacent_bonus": bonuses[0],
        "scattered_bonus": bonuses[1],
        "margin_after": margin,
    }
    holds = (
        base_gap < 0.1
        and bonuses[0] == 1.0
        and bonuses[1] == 0.0
        and margin > 1.0
    )
    return Grade(
        eval_name="proximitygain",
        sentence=(
            "bag-of-words leans 0.09 toward the noun phrase; the span "
            "bonus turns the lean into a 1.09 margin"
        ),
        numbers=numbers,
        holds=holds,
    )
