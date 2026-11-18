"""Support symbols: built in the support's own frame, sized in diameters."""
import numpy as np
import pytest

from flowreel.project import bodies as bodies_mod
from flowreel.project.bodies import End, parse_bodies
from flowreel.scene import supports as S
from flowreel.scene.errors import Checker


def place(outward=True, size=1.0, centre=(0, 0, 0), axis=(1, 0, 0), down=(0, -1, 0)):
    return S.Place.make(centre, axis, outward, down, size)


def bounds(meshes):
    pts = np.vstack([m.points for m in meshes])
    return pts.min(axis=0), pts.max(axis=0)


def test_place_frame_is_right_handed_and_perpendicular():
    p = place(outward=False, down=(0.3, -1, 0))
    assert np.allclose(p.along, (-1, 0, 0)) and np.allclose(p.down, (0, -1, 0))
    assert np.allclose(p.side, np.cross(p.along, p.down))
    q = S.Place.make((0, 0, 0), (0, 1, 0), True, (0, -1, 0), 1.0)   # down along the axis
    assert abs(q.down @ q.along) < 1e-12 and np.isclose(np.linalg.norm(q.down), 1)


def test_clamped_is_the_prototypes_block():
    lo, hi = bounds(S.symbol(End(0.0, "clamped"), place(outward=False)))
    assert np.allclose(lo, (-0.4, -1, -1)) and np.allclose(hi, (0.4, 1, 1))
    lo, hi = bounds(S.symbol(End(12.0, "clamped"), place(centre=(12, 0, 0), size=2.0)))
    assert np.allclose(lo, (11.2, -2, -2)) and np.allclose(hi, (12.8, 2, 2))


def test_pinned_stands_below_the_body():
    lo, hi = bounds(S.symbol(End(0.0, "pinned"), place(down=(0, 0, -1))))
    assert np.isclose(hi[2], -0.5) and np.isclose(lo[2], -1.65)    # from the underside down
    assert np.allclose([lo[0], hi[0]], [-0.7, 0.7])


def test_a_new_kind_is_accepted_by_the_schema():
    @S.register_support("anchor", keys=("depth",), required=("depth",))
    def anchor(end, p):
        return [p.box((-0.1, 0, -0.1), (0.1, end.options.get("depth", 1), 0.1))]

    try:
        body = parse_bodies({"b": {"axis": "x", "ends": [{"at": 0, "support": "anchor",
                                                         "depth": 2}]}}, Checker())["b"]
        assert body.ends[0].support == "anchor"
        assert "anchor" in S.available()
    finally:
        S._symbols.pop("anchor")
        bodies_mod.SUPPORTS.pop("anchor")
        bodies_mod.REQUIRED.pop("anchor")


def test_unknown_symbol():
    with pytest.raises(KeyError, match="no symbol for support 'hinge'"):
        S.symbol(End(0.0, "hinge"), place())


def test_roller_slides_along_free_along():
    meshes = S.symbol(End(0.0, "roller", options={"free_along": "x"}), place(down=(0, 0, -1)))
    rollers = [m for m in meshes if np.ptp(m.points[:, 1]) > 1.1 and np.ptp(m.points[:, 0]) < 0.3]
    assert len(rollers) == 3                                   # axes across the slide (y)
    centres = sorted(round(float(m.center[0]), 3) for m in rollers)
    assert centres == [-0.35, 0.0, 0.35]
    lo, _ = bounds(meshes)
    assert np.isclose(lo[2], -1.86)


def test_spring_coil_reaches_the_ground_block():
    lo, hi = bounds(S.symbol(End(0.0, "spring", options={"stiffness": 1.0}), place(down=(0, -1, 0))))
    assert np.isclose(hi[1], -0.5 + 0.035, atol=0.01) and np.isclose(lo[1], -2.65)


def test_free_is_drawn_only_when_marked():
    assert S.symbol(End(0.0, "free"), place()) == []
    lo, hi = bounds(S.symbol(End(0.0, "free", options={"mark": True}), place()))
    assert np.isclose(hi[1], 0.64, atol=0.01) and abs(hi[0] - lo[0]) < 0.1   # a ring round x


def test_prescribed_points_both_ways_along_its_direction():
    lo, hi = bounds(S.symbol(End(0.0, "prescribed", options={"direction": "y"}), place()))
    assert np.isclose(lo[1], -1.8) and np.isclose(hi[1], 1.8)


def test_tension_pulls_out_of_the_end():
    low_end = S.tension_arrow(place(outward=False))
    assert low_end.points[:, 0].max() <= -0.5 + 1e-9 and np.isclose(low_end.points[:, 0].min(), -2.5)
    assert np.isclose(S.tension_arrow(place(outward=True)).points[:, 0].max(), 2.5)


def test_every_kind_in_the_schema_has_a_symbol():
    assert set(bodies_mod.SUPPORTS) <= set(S.available())
