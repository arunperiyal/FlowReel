"""Grooves in segments: length, gap and stagger along the span (plan Section 5.3)."""
import numpy as np
import pytest

from flowreel.sources.bodies import groove_angle, grooved_cylinder, on_segment, segment_start

# Straight grooves, 4 round the body, segments 1.0 long with 1.0 gaps, neighbours half a
# period apart: spanwise grooves laid like bricks. 0.05 between samples along the span.
BRICKS = {"samples": (241, 361), "caps": False, "turns": 0.0, "phase": 0.0,
          "length": 1.0, "gap": 1.0, "stagger": 0.5}


def depth_at(mesh, x, angle_deg, radius=0.5):
    """Cut depth at spanwise ``x`` on the groove centre at ``angle_deg``."""
    p = mesh.points
    a = np.degrees(np.arctan2(p[:, 1], p[:, 2])) % 360
    near = np.isclose(p[:, 0], x, atol=1e-6) & (np.abs((a - angle_deg + 180) % 360 - 180) < 0.6)
    assert near.any()
    return radius - np.hypot(p[near, 1], p[near, 2]).min()


def test_depth_inside_and_outside_segments():
    mesh = grooved_cylinder(**BRICKS)
    # groove 0 (0 deg): segments [0, 1], [2, 3], ...; gaps (1, 2), (3, 4), ...
    for x in (0.5, 2.5, 10.5):
        assert depth_at(mesh, x, 0) == pytest.approx(0.08)
    for x in (1.5, 3.5, 11.5):
        assert depth_at(mesh, x, 0) == pytest.approx(0.0)


def test_neighbours_are_staggered():
    mesh = grooved_cylinder(**BRICKS)
    # groove 1 (90 deg) is half a period on: segments [1, 2], [3, 4], ...
    assert depth_at(mesh, 1.5, 90) == pytest.approx(0.08)
    assert depth_at(mesh, 0.5, 90) == pytest.approx(0.0)
    # groove 2 is a whole period on: in step with groove 0
    assert depth_at(mesh, 0.5, 180) == pytest.approx(0.08)
    assert segment_start(1, length=1.0, gap=1.0, stagger=0.5) == 1.0
    assert segment_start(3, length=1.0, gap=1.0, stagger=0.5) == 1.0
    assert list(on_segment([0.5, 1.5], 1, length=1.0, gap=1.0, stagger=0.5)) == [False, True]


def test_segment_ends_are_rounded_by_edge():
    sharp = grooved_cylinder(**{**BRICKS, "samples": (1201, 361)}, edge=0.0)
    soft = grooved_cylinder(**{**BRICKS, "samples": (1201, 361)}, edge=0.2)  # 0.1 along x
    # just inside a segment's end: full depth when sharp, part depth when rounded
    assert depth_at(sharp, 0.95, 0) == pytest.approx(0.08)
    assert 0 < depth_at(soft, 0.95, 0) < 0.08
    assert depth_at(soft, 1.05, 0) > 0 and depth_at(sharp, 1.05, 0) == pytest.approx(0.0)


def test_helical_segments_follow_the_groove():
    mesh = grooved_cylinder(samples=(241, 721), caps=False, turns=1.0, length=2.0, gap=1.0)
    for x in (1.0, 4.0):                       # on groove 0's segments [0, 2] and [3, 5]
        assert depth_at(mesh, x, np.degrees(groove_angle(x, 0)) % 360) == pytest.approx(0.08, abs=1e-3)
    assert depth_at(mesh, 2.5, np.degrees(groove_angle(2.5, 0)) % 360) == pytest.approx(0.0)


def test_whole_grooves_are_unchanged():
    base = {"samples": (49, 361), "caps": False}
    whole = grooved_cylinder(**base)
    assert np.array_equal(grooved_cylinder(**base, length=None).points, whole.points)
    assert np.array_equal(grooved_cylinder(**base, length=3.0, gap=0.0).points, whole.points)


def test_cutters_only_on_segments_the_front_is_cutting():
    at = {**BRICKS, "samples": (49, 37)}
    assert grooved_cylinder(**at, cut_front=0.5).field_data["cutters"].shape == (2, 3)  # 0, 2
    angles = np.degrees(np.arctan2(*grooved_cylinder(**at, cut_front=1.5)
                                   .field_data["cutters"][:, 1:].T)) % 360
    assert np.allclose(sorted(angles), [90, 270])                              # 1, 3
    carved = grooved_cylinder(**at, cut_front=0.5)
    x = carved.points[:, 0]
    assert carved["groove"][x > 0.5].max() == 0                   # ahead of the front
    whole = grooved_cylinder(samples=(49, 37), caps=False, cut_front=0.5)
    assert whole.field_data["cutters"].shape == (4, 3)


@pytest.mark.parametrize("params, msg", [
    ({"length": 0.0}, "length must be positive"),
    ({"length": 1.0, "gap": -1.0}, "gap must be at least 0"),
    ({"gap": 1.0}, "need a segment length"),
    ({"stagger": 0.5}, "need a segment length"),
])
def test_errors(params, msg):
    with pytest.raises(ValueError, match=msg):
        grooved_cylinder(samples=(5, 9), **params)
