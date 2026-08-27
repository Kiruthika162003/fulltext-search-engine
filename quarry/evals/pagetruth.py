"""Pagination is walked to the end and audited, lies and limits both.

Against a quiet index the token scheme keeps its whole promise
and this eval walks it two hits at a time to prove it: the
concatenation of all pages equals the one-shot ranking exactly,
nothing repeats, nothing is missing, and the walk terminates
with a None token instead of an infinite tail. The fourth
measurement is the limit, found by measuring rather than
assumed: a document added mid-walk shifts the global BM25
statistics, every score moves, and a hit already served on
page one can rise past the token boundary and be served again,
overlap of exactly one on this fixture. The token is a fence
against offset drift, not against statistics drift, so
mid-walk consistency needs a pinned stats snapshot, and this
eval pins the overlap at one so the day someone adds that
snapshot the eval breaks and demands its own update.
"""

from __future__ import annotations

from quarry.evals.grade import Grade
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index

PAGE_SIZE = 2


def _index() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema)
    for text in (
        "harbor wall at dawn",
        "the harbor master",
        "harbor harbor harbor",
        "a quiet harbor evening",
        "gulls over the harbor",
    ):
        index.add({"body": text})
    index.flush()
    return index


def _walk(index: Index) -> tuple[list[int], int]:
    query = parse("body:harbor")
    externals: list[int] = []
    token = None
    pages = 0
    while True:
        page = search_index(
            index, query, limit=PAGE_SIZE, after=token
        )
        externals.extend(hit.external for hit in page.hits)
        pages += 1
        if page.token is None:
            return externals, pages
        token = page.token
        if pages > 10:
            return externals, pages


def run() -> Grade:
    index = _index()
    query = parse("body:harbor")
    one_shot = [
        hit.external
        for hit in search_index(index, query, limit=100).hits
    ]
    walked, pages = _walk(index)

    matches_one_shot = walked == one_shot
    no_repeats = len(set(walked)) == len(walked)
    complete = set(walked) == set(one_shot)

    fresh = _index()
    first = search_index(
        fresh, parse("body:harbor"), limit=PAGE_SIZE
    )
    fresh.add({"body": "a brand new harbor page"})
    fresh.flush()
    second = search_index(
        fresh,
        parse("body:harbor"),
        limit=PAGE_SIZE,
        after=first.token,
    )
    first_ids = {hit.external for hit in first.hits}
    second_ids = {hit.external for hit in second.hits}
    overlap = len(first_ids & second_ids)

    holds = (
        matches_one_shot
        and no_repeats
        and complete
        and pages == 3
        and overlap == 1
    )
    return Grade(
        eval_name="pagetruth",
        sentence=(
            "token pages are exact and complete on a quiet index; "
            "a mid-walk write shifts BM25 stats and re-serves "
            "exactly one hit, the measured limit of the token"
        ),
        numbers={
            "pages_walked": pages,
            "documents_walked": len(walked),
            "matches_one_shot": int(matches_one_shot),
            "mid_write_overlap": overlap,
        },
        holds=holds,
    )
