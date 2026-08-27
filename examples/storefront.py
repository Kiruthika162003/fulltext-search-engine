"""A storefront hour: business tilt, one row per brand, and a gate.

Run with: python -m examples.storefront
"""

from __future__ import annotations

from quarry.collapse import collapse_report, collapse_search
from quarry.query import parse
from quarry.ratelimit import QueryGate
from quarry.schema import Schema
from quarry.scriptscore import FlagFactor, RecencyFactor, ScorePlan
from quarry.writer import Index

STOCK = [
    ("wool cat blanket", "acme", 90, "yes"),
    ("cat tunnel deluxe", "acme", 40, "yes"),
    ("classic cat post", "acme", 10, "no"),
    ("cat bed round", "cozyco", 80, "yes"),
    ("heated cat pad", "cozyco", 95, "no"),
    ("cat toy mouse", "littleshop", 60, "yes"),
]


def build_shop() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("brand")
    schema.add_numeric("published")
    schema.add_stored("stock")
    schema.seal()
    index = Index(schema=schema)
    for body, brand, published, stock in STOCK:
        index.add(
            {
                "body": body,
                "brand": brand,
                "published": published,
                "stock": stock,
            }
        )
    index.flush()
    return index


def tilted_page(index: Index) -> None:
    plan = ScorePlan(
        factors=[
            RecencyFactor(
                name="fresh", field="published", half_life=50, cap=0.3
            ),
            FlagFactor(
                name="in-stock", field="stock", expected="yes", cap=0.2
            ),
        ]
    )
    print("business tilt on doc 4 (fresh, out of stock):")
    print(plan.explain(0.8, index.document(4), now=100))


def branded_page(index: Index) -> None:
    groups = collapse_search(index, parse("cat"), by="brand")
    print(collapse_report(groups, "brand"))


def gated_traffic() -> None:
    gate = QueryGate(rate=1.0, burst=2, global_ceiling=100)
    outcomes = []
    for number in range(4):
        admission = gate.admit("shopper-7", now=0)
        outcomes.append("y" if admission.allowed else "n")
        if not admission.allowed:
            print(
                f"shopper-7 refused after {number} queries; "
                f"retry in {admission.retry_after}"
            )
            break
    print(f"admissions: {''.join(outcomes)}")


def main() -> int:
    index = build_shop()
    tilted_page(index)
    branded_page(index)
    gated_traffic()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
