"""The axes layer: a triad turning with the camera, arrows at a body end, a ruled box."""
import math

import numpy as np
import pytest
import pyvista as pv

from flowreel.project import PROJECT_FILE
from flowreel.scene.axes import triad_viewport
from flowreel.scene.errors import ConfigError
from flowreel.scene.layers import Frame
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.scene.text import to_display
from flowreel.scene.views import parse_view

from test_layer_supports import Riser

PROJECT = "bodies: {riser: {zone: cyl, axis: x, diameter: 2.0}}\n"
VIEWS = {"side": parse_view({"name": "side", "position": [8, 14, 60], "focal": [20, 0, 0]}),
         "oblique": parse_view({"name": "oblique", "position": [-20, 25, 40],
                                "focal": [20, 0, 0], "up": [0, 1, 0]})}


def scene(tmp_path, layer, view="side", size=(320, 180)):
    (tmp_path / PROJECT_FILE).write_text(PROJECT)
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
            "camera": {"view": view}, "size": [320, 180], "antialias": "none",
            "background": "black", "layers": [{"type": "axes", **layer}]}
    return Scene.make(from_dict(spec, file=str(tmp_path / "s.yml")), Riser(), VIEWS, size=size)


def drawn(sc, inspect):
    """Draw the layer on a plotter with the frame's camera and call ``inspect`` on it."""
    plotter = pv.Plotter(off_screen=True, window_size=list(sc.size))
    try:
        data = sc.data(0)
        sc.camera.view(0, data).apply(plotter.camera)
        frame = Frame(0, 0, 0.0, data, sc.values(0)[0])
        sc.shot.layers[0].draw(plotter, frame)
        return inspect(plotter, frame)
    finally:
        plotter.close()


def screen_angle(ren, a, b):
    (x0, y0, _), (x1, y1, _) = to_display(ren, a), to_display(ren, b)
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


@pytest.mark.parametrize("view", ["side", "oblique"])
def test_triad_turns_with_the_camera(tmp_path, view):
    def check(plotter, frame):
        rens = plotter.ren_win.GetRenderers()
        triad = rens.GetItemAsObject(rens.GetNumberOfItems() - 1)
        assert triad.GetLayer() == plotter.ren_win.GetNumberOfLayers() - 1 > 1
        focal = np.asarray(plotter.camera.focal_point)
        for e in np.eye(3):
            main = screen_angle(plotter.renderer, focal, focal + 1e-3 * e)
            small = screen_angle(triad, np.zeros(3), e)
            assert abs((main - small + 180) % 360 - 180) < 1.0
        return triad.GetViewport()
    viewport = drawn(scene(tmp_path, {"corner": "upper_right", "size": 90}, view), check)
    assert np.allclose(viewport, triad_viewport("upper_right", 90, (320, 180)))


def test_triad_viewport_and_draft_scaling(tmp_path):
    assert np.allclose(triad_viewport("lower_left", 100, (1000, 500)),
                       (0.01, 0.02, 0.11, 0.22))
    full = scene(tmp_path, {"size": 120, "font_size": 20, "width": 2}).values(0)[0]
    half = scene(tmp_path, {"size": 120, "font_size": 20, "width": 2},
                 size=(160, 90)).values(0)[0]
    assert (half["size"], half["font_size"], half["width"]) == (60, 10, 1)
    assert full["size"] == 120


def test_triad_draws_its_arrows_in_the_corner(tmp_path):
    try:
        img = scene(tmp_path, {}).draw(0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    red = (img[:, :, 0] > 120) & (img[:, :, 1] < 110)
    rows, cols = np.nonzero(red)
    assert red.sum() > 20
    assert rows.min() > 180 - 4 - 110 and cols.max() < 4 + 110          # lower left only


def test_arrows_start_at_a_body_end_sized_in_diameters(tmp_path):
    layer = {"style": "arrows", "origin": {"body": "riser", "end": 1}, "unit": "diameters",
             "length": 3, "axes": ["y", "z"], "labels": ["lift", "span"]}
    sc = scene(tmp_path, layer)
    start, body = sc.shot.layers[0].origin(sc.data(0))
    assert body == "riser" and np.allclose(start, [40, 0, 0], atol=0.05)
    assert sc.shot.layers[0].diameter(sc.data(0), body) == 2.0

    def count(plotter, frame):
        return (len(list(plotter.renderer.GetActors())),
                [a.GetInput() for a in plotter.renderer.GetActors2D()])
    actors, labels = drawn(sc, count)
    assert actors == 2 and labels == ["lift", "span"]


@pytest.mark.parametrize("layer, msg", [
    ({"style": "triad", "origin": [0, 0, 0]}, "option of style arrows"),
    ({"style": "arrows"}, "missing key 'origin'"),
    ({"style": "arrows", "origin": {"end": 2}}, "expected 0"),
    ({"axes": ["x", "x"]}, "twice"),
    ({"axes": ["x", "y"], "labels": ["a"]}, "expected 2 labels"),
    ({"colours": ["#ff0000"]}, "expected 3 colours"),
    ({"unit": "diameters"}, "a triad shows directions"),
    ({"style": "pie"}, "pie"),
])
def test_errors(tmp_path, layer, msg):
    with pytest.raises(ConfigError, match=msg):
        scene(tmp_path, layer)
