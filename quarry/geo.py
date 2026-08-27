"""Geo search: near me is a sort key with real trigonometry in it.

Distance ranking needs actual great-circle arithmetic because a
degree of longitude shrinks toward the poles, and a planner that
treats degrees as kilometres ranks Reykjavik wrong all winter. The
haversine here is the standard formula with the standard radius,
returning kilometres, and the sort is distance ascending with ties
by document id. The bounding-box prefilter exists for the same
reason every shortcut in this engine exists, to skip work, and
carries the same obligation: the box is wider than the circle, so
it may admit corner candidates the exact check then rejects, but
it must never exclude a document the circle would keep, which the
tests pin at the box's own corners. Coordinates are validated at
the door: a latitude of 91 is not a place, and finding that out
during a sort is finding it out too late.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from quarry.errors import Invalid

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Point:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise Invalid(
                f"latitude {self.latitude} is not a place on this planet"
            )
        if not -180.0 <= self.longitude <= 180.0:
            raise Invalid(
                f"longitude {self.longitude} wrapped off the map"
            )


def haversine_km(here: Point, there: Point) -> float:
    lat1 = math.radians(here.latitude)
    lat2 = math.radians(there.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(there.longitude - here.longitude)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return round(
        2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 3
    )


@dataclass(frozen=True)
class BoundingBox:
    south: float
    north: float
    west: float
    east: float

    def admits(self, point: Point) -> bool:
        return (
            self.south <= point.latitude <= self.north
            and self.west <= point.longitude <= self.east
        )


def box_around(center: Point, radius_km: float) -> BoundingBox:
    """A box guaranteed to contain the circle, wider near the poles."""
    if radius_km <= 0:
        raise Invalid("a radius of zero is a point wearing a circle")
    lat_degrees = math.degrees(radius_km / EARTH_RADIUS_KM)
    cos_lat = math.cos(math.radians(center.latitude))
    if cos_lat < 1e-6:
        lon_degrees = 180.0
    else:
        lon_degrees = math.degrees(
            radius_km / (EARTH_RADIUS_KM * cos_lat)
        )
    return BoundingBox(
        south=max(-90.0, center.latitude - lat_degrees),
        north=min(90.0, center.latitude + lat_degrees),
        west=max(-180.0, center.longitude - lon_degrees),
        east=min(180.0, center.longitude + lon_degrees),
    )


@dataclass(frozen=True)
class GeoHit:
    external: int
    distance_km: float


def nearest(
    documents: list[tuple[int, Point]],
    center: Point,
    radius_km: float,
    limit: int = 10,
) -> tuple[list[GeoHit], int]:
    """Hits inside the circle, nearest first, plus box-rejects counted."""
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    box = box_around(center, radius_km)
    corner_candidates = 0
    hits: list[GeoHit] = []
    for external, where in documents:
        if not box.admits(where):
            continue
        distance = haversine_km(center, where)
        if distance > radius_km:
            corner_candidates += 1
            continue
        hits.append(GeoHit(external=external, distance_km=distance))
    hits.sort(key=lambda hit: (hit.distance_km, hit.external))
    return hits[:limit], corner_candidates
