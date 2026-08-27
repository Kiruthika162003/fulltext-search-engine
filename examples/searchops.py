"""The ops afternoon: health, pressure, slow habits, and the cold seats.

Run with: python -m examples.searchops
"""

from __future__ import annotations

from quarry.health import HealthBoard, index_canary_check, latency_check
from quarry.metrics import engine_registry
from quarry.slowlog import SlowLog
from quarry.throttle import IndexThrottle
from quarry.tiered import TierLedger


def health_round() -> None:
    board = HealthBoard()
    board.register("index", index_canary_check())
    board.register("query-latency", latency_check("query-latency", 140, budget=100))
    print(board.page())


def pressure_round() -> None:
    throttle = IndexThrottle(capacity=100, guaranteed=5, backlog_limit=50)
    for number in range(40):
        throttle.offer(f"doc-{number}")
    throttle.tick(query_busy_share=0.9)
    print(throttle.pressure_report())
    print(
        f"drain at this pressure: "
        f"{throttle.drain_estimate(query_busy_share=0.9)} tick(s)"
    )


def slowlog_round() -> None:
    log = SlowLog(slow_line=100)
    for _ in range(95):
        log.observe("body:cat", took=3)
    for _ in range(2):
        log.observe("monday report", took=800, terms=11, candidates=4000,
                    segments=3)
    log.observe("one whale", took=1500, terms=2, candidates=80000,
                segments=3)
    print(log.report())


def tier_round() -> None:
    ledger = TierLedger()
    ledger.admit("seg-fresh", sealed_at=100)
    ledger.admit("seg-stale", sealed_at=0)
    ledger.settle(now=100)
    ledger.settle(now=100)
    print(ledger.query_cost_report(["seg-fresh", "seg-stale"]))
    print(f"monthly bill: {ledger.monthly_bill()}")


def metrics_round() -> None:
    registry = engine_registry()
    before = registry.snapshot()
    registry.increment("queries_served", by=98)
    registry.increment("cache_hits", by=60)
    registry.set_gauge("tombstone_share", 0.07)
    for line in registry.delta(before):
        print(f"moved: {line}")


def main() -> int:
    health_round()
    pressure_round()
    slowlog_round()
    tier_round()
    metrics_round()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
