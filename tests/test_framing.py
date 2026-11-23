import math

import numpy as np
import pyvista as pv
import pytest

from flowreel.box import Box
from flowreel.scene.framing import body_centre, fit, follow
from flowreel.scene.views import View

BOX = Box((-2, -2, 0), (2, 2, 4))      # bounding-sphere radius sqrt(16+16+16)/2 = sqrt(12)


def test_fit_perspective_distance_exact():
    v = View((-9, 0, 2), (0, 0, 2), view_angle=60)
    f = fit(v, BOX, margin=1.0)
    r = math.sqrt(12)
    assert f.focal == pytest.approx((0, 0, 2))
    assert np.linalg.norm(np.subtract(f.focal, f.position)) == pytest.approx(r / math.sin(math.radians(30)))
    assert np.allclose(f.direction, v.direction)           # same direction
    # the sphere's tangent rays touch the frame edge: tan(half angle) * distance*cos = r
    assert fit(v, BOX, margin=1.5).distance == pytest.approx(1.5 * f.distance)


def test_fit_parallel_sets_scale_keeps_distance():
    v = View((0, 30, 2), (0, 0, 2), up=(0, 0, -1), parallel=True, parallel_scale=1)
    f = fit(v, BOX, margin=1.1)
    assert f.parallel_scale == pytest.approx(1.1 * math.sqrt(12)) and f.distance == pytest.approx(30)


def test_fit_rejects_bad_input():
    v = View((0, 0, 9), (0, 0, 0))
    with pytest.raises(ValueError):
        fit(v, BOX, margin=0)
    with pytest.raises(ValueError):
        fit(v, Box((1, 1, 1), (1, 1, 1)))


def cylinder():
    return pv.Cylinder(center=(1.0, 0.5, 5.0), direction=(0, 0, 1), radius=0.5, height=10,
                       resolution=24).triangulate().subdivide(2)


def test_body_centre_follows_the_body():
    c = body_centre(cylinder(), station=5.0, axis="z")
    assert c == pytest.approx((1.0, 0.5, 5.0), abs=1e-6)
    shifted = cylinder().translate((0.3, 0, 0), inplace=False)
    assert body_centre(shifted, 5.0)[0] == pytest.approx(1.3, abs=1e-6)


def test_body_centre_without_points_fails():
    with pytest.raises(ValueError, match="no points"):
        body_centre(cylinder(), station=50.0, slab=0.1)


def test_follow_keeps_offset():
    v = View((-10, 0, 0), (0, 0, 0))
    f = follow(v, (3, 4, 5))
    assert f.focal == (3, 4, 5) and f.position == pytest.approx((-7, 4, 5))


def test_a_flat_box_fills_a_picture_of_its_shape():
    """With ``aspect``, a 15 x 7.5 domain seen face on fills a 16:9 picture across, as
    ``project init``'s first view; the sphere fit would leave it at 40 % of the width."""
    view = View((0, 0, 10), (0, 0, 0), (0, 1, 0), name="main")
    box = Box((0, -3.75, -0.05), (15, 3.75, 0.05))
    tight = fit(view, box, margin=1.0, aspect=16 / 9)
    seen = 2 * (tight.distance - 0.05) * math.tan(math.radians(15)) * 16 / 9
    assert seen == pytest.approx(15.0)                # the width just in, at the near face
    assert tight.focal == pytest.approx((7.5, 0, 0))
    assert tight.distance < 0.5 * fit(view, box).distance
    tall = fit(view, box, margin=1.0, aspect=0.25)    # a tall picture: the width decides
    assert 2 * (tall.distance - 0.05) * math.tan(math.radians(15)) * 0.25 == pytest.approx(15.0)
    flat = fit(view.with_(parallel=True), box, margin=1.0, aspect=16 / 9)
    assert flat.parallel_scale == pytest.approx(7.5 * 9 / 16)
    with pytest.raises(ValueError, match="aspect"):
        fit(view, box, aspect=0)


def test_project_inits_first_view_fills_the_picture():
    from flowreel.project.init import cameras_text

    class Domain:
        name = "domain"

        def bounds(self):
            return Box((0, -3.75, -0.05), (15, 3.75, 0.05))
    assert "position: [7.5, 0, 16.584" in cameras_text(Domain())
