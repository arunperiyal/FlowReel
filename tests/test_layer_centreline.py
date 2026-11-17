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
    axis, d, stations, centres, rest = layer.shape(sc.data(0))
    assert axis == "x" and d == 1.0 and len(stations) == 21
    assert np.allclose(centres[:, 1], np.sin(np.pi * stations / 40), atol=0.01)
    tube = layer.tube(stations, centres, d, sc.values(0)[0], rest)
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


# -- from probes, amplify, rest line, envelope -------------------------------------------

PROBES = """\
bodies:
  riser:
    zone: cyl
    axis: x
    diameter: 1.0
    series:
      displacement: {file: disp.csv, by: node, stations: [0, 20, 40]}
"""
# dy at the middle node: 0 at t = 0, 0.8 at t = 0.5, -0.4 at t = 1.0; the ends stay still
DISP = "time,node,dy\n" + "".join(
    f"{t},{n},{v}\n" for t, vals in ((0.0, (0, 0, 0)), (0.5, (0, 0.8, 0)), (1.0, (0, -0.4, 0)))
    for n, v in enumerate(vals))


def probe_scene(tmp_path, layer):
    (tmp_path / "disp.csv").write_text(DISP)
    return scene(tmp_path, {"from": "probes", "origin": [0, 2, 0], **layer}, PROBES)


def test_centreline_from_probes_at_the_frame_time(tmp_path):
    sc = probe_scene(tmp_path, {})
    layer = sc.shot.layers[0]
    axis, d, stations, centres, rest = layer.shape(sc.data(0), time=0.75,
                                                   values=sc.values(0)[0])
    assert list(stations) == [0, 20, 40] and d == 1.0
    assert np.allclose(rest, [[0, 2, 0], [20, 2, 0], [40, 2, 0]])
    assert np.allclose(centres, [[0, 2, 0], [20, 2.2, 0], [40, 2, 0]])   # 0.8 -> -0.4, halfway


def test_amplify_moves_the_tube_not_the_colours(tmp_path):
    sc = probe_scene(tmp_path, {"amplify": 10, "colour_by": "dy", "radius": 0.1})
    layer, v = sc.shot.layers[0], sc.values(0)[0]
    _, d, stations, centres, rest = layer.shape(sc.data(0), time=0.5, values=v)
    tube = layer.tube(stations, centres, d, v, rest)
    assert np.isclose(tube.points[:, 1].max(), 2 + 8 + 0.1, atol=0.01)   # 0.8 drawn as 8
    assert np.isclose(tube["value"].max(), 0.8)                          # coloured by 0.8


def test_envelope_from_probes(tmp_path):
    sc = probe_scene(tmp_path, {"envelope": [0, 20]})
    layer = sc.shot.layers[0]
    lo, hi = layer.envelope(sc.data(0), "riser", np.array([0.0, 20.0, 40.0]))
    assert np.allclose(lo, [0, -0.4, 0]) and np.allclose(hi, [0, 0.8, 0])


class Swinging(Riser):
    """The riser bent by 1, -1 and 0.5 D at steps 0, 10 and 20."""

    def body(self, step, name=None):
        from test_project_measure import tube
        return tube(bend={0: 1.0, 10: -1.0, 20: 0.5}[step])


def test_envelope_from_the_surface(tmp_path):
    (tmp_path / PROJECT_FILE).write_text(PROJECT)
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
            "camera": {"view": "side"}, "size": [64, 48],
            "layers": [{"type": "centreline", "envelope": [0, 20], "rest": True}]}
    sc = Scene.make(from_dict(spec, file=str(tmp_path / "s.yml")), Swinging(), VIEWS)
    lo, hi = sc.shot.layers[0].envelope(sc.data(0), "riser", np.array([10.0, 20.0, 30.0]))
    s = np.sin(np.pi * np.array([10.0, 20.0, 30.0]) / 40)
    assert np.allclose(lo, -s, atol=0.02) and np.allclose(hi, s, atol=0.02)


def test_probes_need_a_declared_axis_and_stations(tmp_path):
    (tmp_path / "disp.csv").write_text("time,dy\n0,0\n")
    project = "bodies: {riser: {zone: cyl, axis: x, series: {displacement: disp.csv}}}\n"
    sc = scene(tmp_path, {"from": "probes"}, project)
    with pytest.raises(ValueError, match="has no stations"):
        sc.shot.layers[0].shape(sc.data(0), time=0.0)
