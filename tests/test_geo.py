from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.geo import (
    BoundingBox,
    Point,
    box_around,
    haversine_km,
    nearest,
)

LONDON = Point(latitude=51.5074, longitude=-0.1278)
PARIS = Point(latitude=48.8566, longitude=2.3522)
REYKJAVIK = Point(latitude=64.1466, longitude=-21.9426)


class TestCoordinates:
    def test_off_planet_latitudes_are_refused(self):
        with pytest.raises(Invalid, match="not a place"):
            Point(latitude=91.0, longitude=0.0)

    def test_wrapped_longitudes_are_refused(self):
        with pytest.raises(Invalid, match="off the map"):
            Point(latitude=0.0, longitude=181.0)


class TestHaversine:
    def test_london_to_paris_is_the_known_distance(self):
        assert haversine_km(LONDON, PARIS) == pytest.approx(344, abs=2)

    def test_distance_is_symmetric(self):
        assert haversine_km(LONDON, PARIS) == haversine_km(PARIS, LONDON)

    def test_zero_distance_to_yourself(self):
        assert haversine_km(LONDON, LONDON) == 0.0


class TestTheBox:
    def test_the_box_contains_the_circle_at_its_corners(self):
        box = box_around(LONDON, radius_km=100)
        for latitude in (box.south, box.north):
            edge = Point(latitude=latitude, longitude=LONDON.longitude)
            assert haversine_km(LONDON, edge) >= 99.9

    def test_the_box_widens_toward_the_poles(self):
        london_box = box_around(LONDON, radius_km=100)
        reykjavik_box = box_around(REYKJAVIK, radius_km=100)
        london_width = london_box.east - london_box.west
        reykjavik_width = reykjavik_box.east - reykjavik_box.west
        assert reykjavik_width > london_width

    def test_a_zero_radius_is_refused(self):
        with pytest.raises(Invalid, match="wearing a circle"):
            box_around(LONDON, radius_km=0)

    def test_admits_is_inclusive_at_the_edge(self):
        box = BoundingBox(south=0, north=10, west=0, east=10)
        assert box.admits(Point(latitude=10, longitude=10))
        assert not box.admits(Point(latitude=10.1, longitude=10))


class TestNearest:
    def cafes(self) -> list[tuple[int, Point]]:
        return [
            (0, Point(latitude=51.51, longitude=-0.13)),
            (1, Point(latitude=51.60, longitude=-0.20)),
            (2, PARIS),
            (3, REYKJAVIK),
        ]

    def test_nearest_first_inside_the_circle(self):
        hits, _ = nearest(self.cafes(), LONDON, radius_km=50)
        assert [hit.external for hit in hits] == [0, 1]
        assert hits[0].distance_km < hits[1].distance_km

    def test_the_circle_excludes_what_the_box_admitted(self):
        documents = [
            (9, Point(latitude=51.5074 + 0.85, longitude=-0.1278 + 1.3))
        ]
        hits, corner_rejects = nearest(documents, LONDON, radius_km=100)
        assert hits == []
        assert corner_rejects == 1

    def test_paris_is_outside_a_small_london_circle(self):
        hits, _ = nearest(self.cafes(), LONDON, radius_km=300)
        assert all(hit.external != 2 for hit in hits)

    def test_the_limit_caps_after_sorting(self):
        hits, _ = nearest(self.cafes(), LONDON, radius_km=5000, limit=2)
        assert [hit.external for hit in hits] == [0, 1]

    def test_zero_limits_are_refused(self):
        with pytest.raises(Invalid):
            nearest(self.cafes(), LONDON, radius_km=10, limit=0)
