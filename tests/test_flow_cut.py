"""Planar cuts of a step (compose/flow_cut.py) on the generated cylinder case."""
import sys
from pathlib import Path

import numpy as np
import pytest

from flowreel.box import Box
from flowreel.compose import flow_cut as fc
from flowreel.sources.plt import PltSource

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    folder = case.write_case(tmp_path_factory.mktemp("cylinder"))
    return PltSource(folder / "case", cache=None)


class Counting:
    """A source that records the crops it is asked for."""

    def __init__(self, source):
        self.source, self.crops = source, []

    def __getattr__(self, name):
        return getattr(self.source, name)

    def flow(self, step, fields, crop):
        self.crops.append((crop, list(fields)))
        return self.source.flow(step, fields, crop)


def box(depth=0.6):
    return fc.plane_box(fc.station_plane("x", 2.0), (1, 2), (-3, -3), (3, 3), depth)


def test_plane_axes():
    assert fc.plane_axes(0) == (1, 2) and fc.plane_axes(2) == (0, 1)
    assert fc.plane_axes(0, ["z", "y"]) == (2, 1)
    with pytest.raises(ValueError, match="normal"):
        fc.plane_axes(0, ["x", "y"])
    with pytest.raises(ValueError, match="two different"):
        fc.plane_axes(0, ["y", "y"])


def test_plane_box_is_a_slab_round_the_plane():
    b = fc.plane_box(fc.Plane(0, 2.0), (2, 1), (-1, -2), (3, 4), 0.5)
    assert b == Box((1.5, -2, -1), (2.5, 4, 3))


def test_cut_carries_derived_and_given_fields(source):
    cut = fc.read_cut(source, 20, fc.station_plane("x", 2.0), ["vorticity_x", "p", "U"], box())
    assert cut.axes == (1, 2) and cut.points.shape[1] == 2
    assert cut.triangles.shape[1] == 3 and cut.triangles.max() < len(cut.points)
    # a solid rotation at OMEGA: spanwise vorticity 2 OMEGA everywhere
    assert np.allclose(cut.values["vorticity_x"], 2 * case.OMEGA, atol=1e-4)
    assert np.allclose(cut.values["p"], case.SLOPE * cut.points[:, 1], atol=1e-5)
    assert np.allclose(cut.values["U"], case.SHEAR * cut.points[:, 1], atol=1e-5)
    # in the plane, away from the body's centre by r: the rotation's speed OMEGA r
    yc = case.centre_y(source.time(20))
    v = cut.velocity
    assert np.allclose(v[:, 1], case.SPEED - case.OMEGA * cut.points[:, 1], atol=1e-5)
    assert np.allclose(v[:, 2], case.OMEGA * (cut.points[:, 0] - yc), atol=1e-5)
    assert cut.triangulation().triangles.shape == cut.triangles.shape


def test_axes_order_swaps_the_picture(source):
    cut = fc.read_cut(source, 0, fc.station_plane("x", 2.0), ["p"], box(), axes=(2, 1))
    assert np.allclose(cut.values["p"], cut.points[:, 0], atol=1e-5)    # z is across


def test_cut_reads_only_the_box_and_pressure_only_when_needed(source):
    counting = Counting(source)
    plane = fc.station_plane("x", 2.0)
    fc.read_cut(counting, 0, plane, ["vorticity_x"], box())
    cut = fc.read_cut(counting, 0, plane, ["pressure_coefficient"], box(0.9),
                      params={"rho": 2.0, "u_inf": 1.0})
    (crop1, fields1), (crop2, fields2) = counting.crops
    assert crop1 == box() and fields1 == ["U", "V", "W"]
    assert crop2 == box(0.9) and fields2 == ["U", "V", "W", "p"]
    assert np.allclose(cut.values["pressure_coefficient"], cut.points[:, 1], atol=1e-5)


def test_window_reads_fewer_nodes_than_the_step(source):
    flow = source.flow(0, ["U"], box(0.6))
    whole = source.flow(0, ["U"], None)
    assert 0 < flow.n_points < whole.n_points / 2


def test_empty_cuts_are_errors(source):
    with pytest.raises(ValueError, match="no cell read crosses"):
        fc.read_cut(source, 0, fc.station_plane("x", 2.0), ["U"], box(0.1))
    with pytest.raises(ValueError, match="x = 9 is empty"):
        fc.read_cut(source, 0, fc.station_plane("x", 9.0),
                    ["U"], fc.plane_box(fc.station_plane("x", 9.0), (1, 2), (-3, -3), (3, 3), 0.6))
    with pytest.raises(ValueError, match="no field 'nonsense'"):
        fc.read_cut(source, 0, fc.station_plane("x", 2.0), ["nonsense"], box())


def test_outline_is_the_body_in_the_plane(source):
    yc = case.centre_y(source.time(30))
    curves = fc.outlines(source.body(30, "cyl"), fc.station_plane("x", 1.0), (1, 2))
    assert len(curves) == 1
    r = np.hypot(curves[0][:, 0] - yc, curves[0][:, 1])
    assert np.allclose(r, case.RADIUS, atol=1e-6) and len(curves[0]) >= case.AROUND
    angle = np.unwrap(np.arctan2(curves[0][:, 1], curves[0][:, 0] - yc))
    assert abs(angle[-1] - angle[0]) == pytest.approx(2 * np.pi, abs=0.2)   # once round, in order
    assert fc.outlines(source.body(0, "cyl"), fc.station_plane("x", 7.0), (1, 2)) == []
    inside = fc.inside(curves, np.array([yc, yc + 1.0]), np.array([0.0, 0.0]))
    assert inside.tolist() == [True, False]


def test_body_centre_and_velocity(source):
    c = fc.body_centre(source, 20, "cyl", "x", 2.0)
    assert np.allclose(c, [2.0, case.centre_y(1.0), 0], atol=1e-6)
    for step in (0, 10, 30):                      # one-sided at the ends
        assert np.allclose(fc.body_velocity(source, step, "cyl", "x", 2.0), [0, case.SPEED, 0],
                           atol=1e-6)
