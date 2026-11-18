"""The supports layer: symbols at the declared ends, on the body, sized in diameters."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.project import PROJECT_FILE
from flowreel.scene.layers import Frame
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.scene.views import parse_view

from conftest import ToySource
from test_project_measure import tube

PROJECT = """\
bodies:
  riser:
    zone: cyl
    axis: x
    diameter: 1.0
    ends:
      - {at: 0.0, support: pinned}
      - {at: 40.0, support: roller, free_along: x, tension: true}
      - {at: 20.0, support: spring, stiffness: 5}
"""
VIEWS = {"side": parse_view({"name": "side", "position": [20, 0, 60], "focal": [20, 0, 0]}),
         "far": parse_view({"name": "far", "position": [20, 0, 4000], "focal": [20, 0, 0]})}


class Riser(ToySource):
    """A riser 40 D long along x, bent 1 D in y at mid-span."""

    name = "riser"

    def bodies(self):
        return ["cyl"]

    def body(self, step, name=None):
        return tube(bend=1.0)


def scene(tmp_path, layer=None, project=PROJECT, view="side"):
    (tmp_path / PROJECT_FILE).write_text(project)
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 2},
            "camera": {"view": view}, "size": [320, 180], "antialias": "none",
            "background": "black",
            "layers": [{"type": "supports", "colour": "#ff0000", "arrow_colour": "#00ff00",
                        **(layer or {})}]}
    return Scene.make(from_dict(spec, file=str(tmp_path / "s.yml")), Riser(), VIEWS)


def places(sc, height=180):
    plotter = pv.Plotter(off_screen=True, window_size=[320, height])
    sc.camera.view(0, sc.data(0)).apply(plotter.camera)
    layer = sc.shot.layers[0]
    try:
        return layer.places(plotter, Frame(0, 0, 0.0, sc.data(0), sc.values(0)[0]))
    finally:
        plotter.close()


def test_supports_stand_on_the_body_at_their_stations(tmp_path):
    got = places(scene(tmp_path))
    assert [e.support for e, _ in got] == ["pinned", "roller", "spring"]
    centres = np.array([p.centre for _, p in got])
    assert np.allclose(centres[:, 0], [0, 40, 20])
    assert np.allclose(centres[:, 1], [0, 0, 1.0], atol=0.02)      # on the bend at mid-span
    assert [bool(p.along[0] > 0) for _, p in got] == [False, True, True]
    assert all(np.isclose(p.size, 1.0) for _, p in got)


def test_size_ends_and_min_pixels(tmp_path):
    got = places(scene(tmp_path, {"ends": [1], "size": 2.0}))
    assert [e.at for e, _ in got] == [40.0] and np.isclose(got[0][1].size, 2.0)
    # side: a diameter is 180 / (2 * 60 * tan 15 deg) = 5.6 px; far: 0.084 px
    far = places(scene(tmp_path, {"min_pixels": 4}, view="far"))
    assert all(np.isclose(p.size, 4 * 2 * 4000 * np.tan(np.radians(15)) / 180, rtol=1e-3)
               for _, p in far)                                     # enlarged to 4 px
    near = places(scene(tmp_path, {"min_pixels": 4}))
    assert all(np.isclose(p.size, 1.0) for _, p in near)            # big enough already


def test_supports_are_drawn(tmp_path):
    try:
        img = scene(tmp_path).draw(0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    red = (img[:, :, 0] > 100) & (img[:, :, 1] < 60)
    green = (img[:, :, 1] > 100) & (img[:, :, 0] < 60)
    assert red.sum() > 40 and green.sum() > 10                     # symbols and tension


@pytest.mark.parametrize("layer, project, msg", [
    ({"body": "pipe"}, PROJECT, "no body 'pipe'"),
    ({"ends": [5]}, PROJECT, "has 3 ends, no end 5"),
    ({}, "bodies: {riser: {zone: cyl, axis: x}}\n", None),           # nothing to draw
    ({"body": "riser"}, "bodies: {riser: {zone: cyl, axis: x}}\n", "declares no ends"),
    ({}, "bodies: {}\n", "no bodies are declared"),
])
def test_errors(tmp_path, layer, project, msg):
    sc = scene(tmp_path, layer, project)
    if msg is None:
        assert places(sc) == []
        return
    with pytest.raises((ValueError, KeyError), match=msg):
        places(sc)
