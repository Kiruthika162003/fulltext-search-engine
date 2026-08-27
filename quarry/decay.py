"""Popularity decay: yesterday's heat cools on a schedule, not a whim.

Autocomplete weights, trending baselines, and click books all
accumulate forever unless something forgets, and the forgetting
must be principled or the feature drifts toward a hall of fame of
2019. Exponential decay is the principle: every stored weight
halves over the declared half life, applied lazily at read time
from the last-touched stamp, so nothing pays for the forgetting
until it is consulted. The floor prunes what decayed to noise,
with the pruned mass reported, because memory reclaimed silently
is a leak in reverse that nobody can audit. Lazy decay's one trap
is stamped: reading refreshes the stamp only when the caller says
so, since a monitor that reads every minute would otherwise keep
everything warm forever, turning observation into preservation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

HALF_LIFE = 100
NOISE_FLOOR = 0.01


@dataclass
class DecayedWeight:
    weight: float
    stamped_at: int


@dataclass
class DecayBook:
    half_life: int = HALF_LIFE
    noise_floor: float = NOISE_FLOOR
    weights: dict[str, DecayedWeight] = field(default_factory=dict)
    pruned_mass: float = 0.0

    def __post_init__(self) -> None:
        if self.half_life <= 0:
            raise Invalid("a half life must be positive")
        if self.noise_floor <= 0:
            raise Invalid(
                "a floor of zero keeps every ghost forever"
            )

    def _decayed(self, held: DecayedWeight, now: int) -> float:
        age = now - held.stamped_at
        if age < 0:
            raise Invalid(
                "a weight stamped in the future; the clock went "
                "backwards and the book cannot decay along"
            )
        return held.weight * (0.5 ** (age / self.half_life))

    def bump(self, key: str, now: int, by: float = 1.0) -> None:
        if by <= 0:
            raise Invalid("a bump must add something")
        held = self.weights.get(key)
        current = self._decayed(held, now) if held else 0.0
        self.weights[key] = DecayedWeight(
            weight=current + by, stamped_at=now
        )

    def read(
        self, key: str, now: int, refresh_stamp: bool = False
    ) -> float:
        held = self.weights.get(key)
        if held is None:
            return 0.0
        value = self._decayed(held, now)
        if refresh_stamp:
            self.weights[key] = DecayedWeight(
                weight=value, stamped_at=now
            )
        return round(value, 6)

    def prune(self, now: int) -> int:
        doomed = []
        for key, held in self.weights.items():
            value = self._decayed(held, now)
            if value < self.noise_floor:
                doomed.append(key)
                self.pruned_mass += value
        for key in doomed:
            del self.weights[key]
        return len(doomed)

    def top(self, now: int, limit: int = 5) -> list[tuple[str, float]]:
        if limit <= 0:
            raise Invalid("a top list with no rows should not print")
        rows = [
            (key, self.read(key, now)) for key in self.weights
        ]
        rows.sort(key=lambda row: (-row[1], row[0]))
        return rows[:limit]

    def ledger_line(self) -> str:
        live = len(self.weights)
        return (
            f"{live} key(s) held, {self.pruned_mass:.4f} decayed mass "
            f"pruned, half life {self.half_life}"
        )
