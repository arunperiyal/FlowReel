import math

import numpy as np
import pytest

from flowreel.scene.projection import project
from flowreel.scene.views import View

SIZE = (200, 100)


def test_focal_point_is_the_centre():
    v = View((0, 0, 10), (0, 0, 0))
    assert project(v, (0, 0, 0), SIZE)[0] == pytest.approx((100, 50, 10))


def test_perspective_exact_edges():
    v = View((0, 0, 10), (0, 0, 0), up=(0, 1, 0), view_angle=90)
    # at the focal plane (depth 10) the half height is 10 * tan(45 deg) = 10, half width 20
    out = project(v, [(0, 10, 0), (20, 0, 0), (-20, -10, 0)], SIZE)
    assert out[:, :2] == pytest.approx(np.array([(100, 0), (200, 50), (0, 100)]), abs=1e-9)


def test_screen_axes_follow_up_and_handedness():
    # looking down -z with up=+y, +x is to the right (right-handed)
    v = View((0, 0, 10), (0, 0, 0))
    assert project(v, (1, 0, 0), SIZE)[0, 0] > 100 and project(v, (0, 1, 0), SIZE)[0, 1] < 50


def test_nearer_points_are_larger():
    v = View((0, 0, 10), (0, 0, 0))
    near, far = project(v, [(1, 0, 5), (1, 0, -5)], SIZE)
    assert near[0] - 100 == pytest.approx(3 * (far[0] - 100)) and near[2] < far[2]


def test_parallel_ignores_depth():
    v = View((0, 0, 10), (0, 0, 0), parallel=True, parallel_scale=5)
    a, b = project(v, [(1, 1, 5), (1, 1, -5)], SIZE)
    assert a[:2] == pytest.approx(b[:2])
    assert a[1] == pytest.approx(50 - 1 / 5 * 50)


def test_behind_camera_is_nan():
    v = View((0, 0, 10), (0, 0, 0))
    out = project(v, (0, 0, 20), SIZE)
    assert np.isnan(out[0, :2]).all() and out[0, 2] == pytest.approx(-10)


def test_matches_vtk_camera():
    import pyvista as pv
    v = View((3, 4, 12), (0.5, 0, 1), up=(0, 1, 0.2), view_angle=40)
    pl = pv.Plotter(off_screen=True, window_size=SIZE)
    v.apply(pl.camera)
    pl.camera.clipping_range = (0.1, 100)
    pt = (1.0, -0.5, 2.0)
    ren = pl.renderer
    ren.SetWorldPoint(*pt, 1.0)
    ren.WorldToView()
    vx, vy, _ = ren.GetViewPoint()
    pl.close()
    mine = project(v, pt, SIZE)[0]
    assert mine[0] == pytest.approx((vx + 1) / 2 * SIZE[0], abs=1e-6)
    assert mine[1] == pytest.approx((1 - vy) / 2 * SIZE[1], abs=1e-6)
