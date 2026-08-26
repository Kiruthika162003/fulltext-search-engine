"""Identical documents tie exactly, and the tie is a promise, not luck.

The fixture corpus carries two documents with identical text, and
this eval pins what every ranking layer promises about them: the
scores are equal to the last decimal because the same bytes under
the same statistics must price the same, the order between them is
by external id every single time, and the pagination boundary
cannot split them nondeterministically: walking the corpus in
pages and walking it whole produce the same sequence. Determinism
under ties is the property regressions break silently, because
every individual run still looks reasonable, and only the diff
between two runs, or two page sizes, shows the shuffle.
"""

from __future__ import annotations

from quarry.evals.corpus import build_engine
from quarry.evals.grade import Grade


def run() -> Grade:
    engine = build_engine()
    first = engine.search("gentle weather", limit=10)
    twins = [
        hit
        for hit in first.hits
        if hit.external in (10, 11)
    ]
    scores_equal = (
        len(twins) == 2 and twins[0].score == twins[1].score
    )
    id_ordered = [hit.external for hit in twins] == [10, 11]
    repeated = engine.search("gentle weather", limit=10)
    stable = [hit.external for hit in first.hits] == [
        hit.external for hit in repeated.hits
    ]
    paged_one = engine.search("gentle weather", limit=1)
    paged_rest = engine.search(
        "gentle weather", limit=10, after=paged_one.token
    )
    walked = [hit.external for hit in paged_one.hits] + [
        hit.external for hit in paged_rest.hits
    ]
    whole = [hit.external for hit in first.hits]
    pages_agree = walked == whole
    numbers = {
        "twin_scores_equal": scores_equal,
        "twins_id_ordered": id_ordered,
        "identical_runs_identical": stable,
        "page_walk_matches_whole": pages_agree,
    }
    holds = scores_equal and id_ordered and stable and pages_agree
    return Grade(
        eval_name="twinties",
        sentence=(
            "the twins score identically, order by id, and no page "
            "boundary can split them differently than the whole walk"
        ),
        numbers=numbers,
        holds=holds,
    )
