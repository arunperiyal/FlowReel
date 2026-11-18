"""A body's centre, centreline, diameter and long axis, measured from its surface."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.project.bodies import Body
from flowreel.project.measure import centre, centreline, default_slab, diameter, long_axis
from flowreel.project.names import DeclaredSource
from flowreel.scene.camera import ShotCamera
from flowreel.scene.errors import Checker
from flowreel.scene.layers import FrameData

from conftest import ToySource
from test_render import VIEWS

LENGTH, RADIUS = 40.0, 0.5


def tube(bend=0.0, length=LENGTH, rings=401, sides=32):
    """A cylinder along x from 0 to ``length``, diameter 1, without caps, its points on
    exact rings, its axis bent to ``y = bend * sin(pi x / length)``."""
    x = np.linspace(0, length, rings)
    theta = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    xx, tt = np.meshgrid(x, theta, indexing="ij")
    pts = np.column_stack([xx.ravel(), RADIUS * np.cos(tt.ravel()), RADIUS * np.sin(tt.ravel())])
    pts[:, 1] += bend * np.sin(np.pi * pts[:, 0] / length)
    i, j = np.meshgrid(np.arange(rings - 1), np.arange(sides), indexing="ij")
    a, b = i * sides + j, i * sides + (j + 1) % sides
    quads = np.column_stack([np.full(a.size, 4), a.ravel(), b.ravel(),
                             b.ravel() + sides, a.ravel() + sides])
    return pv.PolyData(pts, quads.ravel())


def test_straight_tube():
    s = tube()
    assert long_axis(s) == "x" and diameter(s, "x") == pytest.approx(1.0, rel=1e-6)
    stations, centres = centreline(s, "x", count=11)
    assert stations[0] > 0 and stations[-1] < LENGTH and len(stations) == 11
    assert np.allclose(centres[:, 0], stations) and np.allclose(centres[:, 1:], 0, atol=1e-6)


def test_bent_tube_centreline_follows_the_bend():
    s = tube(bend=1.5)
    stations, centres = centreline(s, "x", stations=[10.0, 20.0, 30.0])
    want = 1.5 * np.sin(np.pi * np.array([10.0, 20.0, 30.0]) / LENGTH)
    assert np.allclose(centres[:, 1], want, atol=0.02)
    assert diameter(s, "x") == pytest.approx(1.0, rel=0.005)  # the bend is not the width
    assert centre(s, 20.0, "x") == pytest.approx((20.0, 1.5, 0.0), abs=0.02)


def test_a_long_body_is_cut_thin():
    long = tube(length=500.0, rings=2001)
    assert default_slab(long, "x") == pytest.approx(0.25, rel=0.01)  # a quarter D, not 10 D
    assert default_slab(tube(length=10.0), "x") == pytest.approx(0.2)   # 2% of 10
    assert diameter(long, "x") == pytest.approx(1.0, rel=1e-6)


def test_a_body_that_is_not_slender():
    ball = pv.Sphere(radius=0.3)
    assert long_axis(ball) is None
    assert diameter(ball) == pytest.approx(0.6, rel=0.01)    # a polygon, a bit inside
    assert long_axis(tube(length=2.0)) is None                # 2 D long: not slender


def test_no_points_in_the_section():
    with pytest.raises(ValueError, match="no points within"):
        centre(tube(rings=5), 5.0, "x", slab=0.01)


class Riser(ToySource):
    name = "riser"

    def bodies(self):
        return ["cyl"]

    def body(self, step, name=None):
        return tube(bend=1.0)


def test_follow_takes_the_axis_and_diameter_from_the_declaration():
    src = DeclaredSource(Riser(), {"riser": Body("riser", "cyl", axis="x", diameter=1.0)})
    data = FrameData(src, 0)
    camera = ShotCamera({"view": "side", "follow": "riser", "station": 20.0}, VIEWS, {}, Checker())
    assert camera.view(0, data).focal == pytest.approx((20.0, 1.0, 0.0), abs=0.02)
    # the same as an undeclared body with the axis written in the shot
    plain = ShotCamera({"view": "side", "follow": "cyl", "station": 20.0, "axis": "x"},
                       VIEWS, {}, Checker())
    assert plain.view(0, FrameData(Riser(), 0)).focal == pytest.approx(
        camera.view(0, data).focal, abs=0.01)
