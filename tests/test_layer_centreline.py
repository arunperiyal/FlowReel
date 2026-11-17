"""The centreline layer: a beam body's axis as a tube, coloured by displacement."""
import numpy as np
import pytest

from flowreel.project import PROJECT_FILE
from flowreel.scene.centreline import displacement_values, rest_line
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.scene.views import parse_view

from test_layer_supports import Riser          # a riser 40 D long along x, bent 1 D in y

VIEWS = {"side": parse_view({"name": "side", "position": [20, 0, 60], "focal": [20, 0, 0]})}
PROJECT = "bodies: {riser: {zone: cyl, axis: x, diameter: 1.0}}\n"


def scene(tmp_path, layer=None, project=PROJECT):
    (tmp_path / PROJECT_FILE).write_text(project)
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
            "camera": {"view": "side"}, "size": [320, 180], "antialias": "none",
            "layers": [{"type": "centreline", **(layer or {})}]}
    return Scene.make(from_dict(spec, file=str(tmp_path / "s.yml")), Riser(), VIEWS)


def test_rest_line_and_displacement_exact():
    stations = [0.0, 1.0, 2.0]
    centres = [[0, 0, 0], [1, 3, 4], [2, 0, 2]]
    rest = rest_line(stations, centres)
    assert np.allclose(rest, [[0, 0, 0], [1, 0, 1], [2, 0, 2]])
    assert np.allclose(displacement_values("displacement", centres, rest), [0, np.hypot(3, 3), 0])
    assert np.allclose(displacement_values("dy", centres, rest), [0, 3, 0])
    assert np.allclose(displacement_values("dz", centres, rest), [0, 3, 0])


def test_the_tube_follows_the_bend(tmp_path):
    sc = scene(tmp_path, {"count": 21, "radius": 0.2, "colour_by": "dy", "range": [-1, 1]})
    layer = sc.shot.layers[0]
    axis, d, stations, centres = layer.shape(sc.data(0))
    assert axis == "x" and d == 1.0 and len(stations) == 21
    assert np.allclose(centres[:, 1], np.sin(np.pi * stations / 40), atol=0.01)
    tube = layer.tube(stations, centres, d, sc.values(0)[0])
    assert np.isclose(np.ptp(tube.points[:, 2]), 0.4, atol=0.01)     # 0.2 D radius
    assert tube["value"].max() == pytest.approx(1.0, abs=0.02)        # dy at mid-span


def test_drawn(tmp_path):
    try:
        img = scene(tmp_path, {"colour": "#ff0000"}).draw(0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert ((img[:, :, 0] > 100) & (img[:, :, 1] < 60)).sum() > 200


def test_a_body_that_is_not_slender(tmp_path):
    from conftest import ToySource
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
            "camera": {"view": "side"}, "size": [32, 24], "layers": [{"type": "centreline"}]}
    sc = Scene.make(from_dict(spec, file=str(tmp_path / "x" / "s.yml")), ToySource(), VIEWS)
    with pytest.raises(ValueError, match="'sphere' is not slender"):
        sc.shot.layers[0].shape(sc.data(0))
