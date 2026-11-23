"""The streamlines layer: lines along the velocity from seed points (Phase 8, branch 5)."""
import numpy as np
import pytest
import pyvista as pv

import flowreel.scene.flow_layers  # noqa: F401
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker, ConfigError
from tests.conftest import ToySource


def make(**spec):
    base = {"type": "streamlines",
            "seeds": {"line": {"from": [0.25, 0.0, 0.5], "to": [0.75, 0.0, 0.5], "count": 3}}}
    return L.build({**base, **spec}, Checker("s.yml", ("layers", 0)))


def frame(layer, flow=None, source=None, step=0):
    src = source or ToySource()
    flow = flow if flow is not None else src.flow(step, ["U", "V", "W"], None)
    return L.Frame(0, step, 0.0, L.FrameData(src, step, flow), layer.values(0))


def lines_of(layer, **kw):
    f = frame(layer, **kw)
    return layer.mesh(f, f.values)


def uniform():
    g = pv.ImageData(dimensions=(11, 5, 5), spacing=(0.2, 0.25, 0.25),
                     origin=(0, -0.5, 0)).cast_to_unstructured_grid()
    g.point_data["U"] = np.ones(g.n_points)
    g.point_data["V"] = np.zeros(g.n_points)
    g.point_data["W"] = np.zeros(g.n_points)
    return g


def test_a_uniform_flow_gives_straight_lines_along_it():
    layer = make(seeds={"line": {"from": [1.0, -0.25, 0.5], "to": [1.0, 0.25, 0.5], "count": 3}})
    lines = lines_of(layer, flow=uniform())
    assert lines.n_lines == 6                              # each seed, one line each way
    pts = lines.points
    assert np.ptp(pts[:, 0]) > 1.5                        # along x, both ways
    for y in (-0.25, 0.0, 0.25):                         # each line keeps its y and z
        on = np.isclose(pts[:, 1], y, atol=1e-6)
        assert on.any() and np.allclose(pts[on, 2], 0.5)
    assert np.isclose(pts[:, 1], -0.25, atol=1e-6).sum() + np.isclose(pts[:, 1], 0.0, atol=1e-6).sum() \
        + np.isclose(pts[:, 1], 0.25, atol=1e-6).sum() == lines.n_points


def test_a_vortex_gives_closed_circles():
    lines = lines_of(make(length=10.0))
    r = np.hypot(lines.points[:, 0], lines.points[:, 1])
    for seed in (0.25, 0.5, 0.75):                       # each line stays on its circle
        near = np.isclose(r, seed, atol=0.02)
        assert near.sum() > 20
    assert np.all(np.min(np.abs(r[:, None] - np.array([0.25, 0.5, 0.75])), axis=1) < 0.02)


def test_plane_seeds_and_tubes():
    layer = make(seeds={"plane": {"normal": "z", "position": 0.5, "lo": [0.2, 0.2],
                                  "hi": [0.6, 0.6], "counts": [2, 3]}})
    assert len(layer.seed_points(None, layer.values(0)["seeds"])) == 6
    tubes = make(style="tubes", radius=0.02)
    mesh = lines_of(tubes)
    assert mesh.n_cells > 0 and mesh.n_lines == 0          # surfaces, not lines


def test_round_seeds_ring_the_body():
    z = ToySource().body(0).points[:, 2]
    station = float(z[np.argmin(np.abs(z - 0.5))])         # a ring of the sphere's points
    layer = make(seeds={"round": {"station": station, "radius": 1.0, "count": 8}})
    pts = layer.seed_points(frame(layer).data, layer.values(0)["seeds"])
    assert pts.shape == (8, 3) and np.allclose(pts[:, 2], station)
    r = np.hypot(*(pts[:, :2] - pts[:, :2].mean(axis=0)).T)
    assert np.allclose(r, r[0]) and r[0] > 0


def test_relative_subtracts_the_bodys_speed(monkeypatch):
    """A body moving with the flow sees no flow: its lines are only their seeds."""
    from flowreel.compose import flow_cut
    monkeypatch.setattr(flow_cut, "body_velocity", lambda *a, **k: np.array([1.0, 0.0, 0.0]))
    layer = make(seeds={"line": {"from": [1.0, -0.25, 0.5], "to": [1.0, 0.25, 0.5], "count": 3}},
                 relative={"body": "sphere", "station": 0.5})
    lines = lines_of(layer, flow=uniform())
    assert lines is None or np.ptp(lines.points[:, 0]) < 1e-6


@pytest.mark.parametrize("spec, message", [
    ({"seeds": {}}, "exactly one of"),
    ({"seeds": {"line": {"from": [0, 0], "to": [1, 0, 0]}}}, "expected 3 numbers"),
    ({"seeds": {"plane": {"normal": "w", "position": 0, "lo": [0, 0], "hi": [1, 1],
                          "counts": [2, 2]}}}, "normal"),
    ({"seeds": {"round": {"count": 4}}}, "needs 'station'"),
    ({"length": -1}, "must be positive"),
    ({"relative": True}, "round seeds"),
    ({"relative": "yes"}, "expected true, false"),
])
def test_bad_options_name_the_key(spec, message):
    with pytest.raises(ConfigError, match=message):
        make(**spec)


def test_a_frame_draws_the_lines():
    from flowreel.scene.rendering import Scene
    from tests.test_render import VIEWS, toy_shot
    shot = toy_shot(layers=[{"type": "streamlines", "colour": "#ff0000", "width": 3,
                             "seeds": {"line": {"from": [0.25, 0, 0.5], "to": [0.75, 0, 0.5],
                                                "count": 3}}}])
    try:
        image = Scene.make(shot, ToySource(), VIEWS).draw(0)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    red = (image[..., 0] > 150) & (image[..., 1] < 80) & (image[..., 2] < 80)
    assert red.sum() > 20
