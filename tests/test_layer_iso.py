import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.errors import Checker
from flowreel.scene import layers as L
import flowreel.scene.flow_layers  # noqa: F401  (registers the layers)
from tests.conftest import ToySource


def make(spec):
    return L.build({"type": "iso", "field": "speed", **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, index=0, step=0):
    src = ToySource()
    data = L.FrameData(src, step, src.flow(step, ["U", "V", "W"], None))
    return L.Frame(index, step, 0.0, data, layer.values(index))


def test_surface_is_the_level_set_and_needs_fields():
    layer = make({"level": 0.5})
    f = frame_for(layer)
    mesh = layer.surface(f, f.values)
    assert mesh.n_points and np.allclose(mesh["speed"], 0.5, atol=1e-6)


def test_level_is_a_track():
    layer = make({"level": {"keys": [[0, -0.1], [10, -1.0]], "ease": "linear"}})
    assert layer.values(5)["level"] == pytest.approx(-0.55)


def test_wall_gap_hides_near_wall():
    layer = make({"level": 0.5})
    f = frame_for(layer)
    near = layer.surface(f, f.values)
    gap = layer.surface(f, {**f.values, "wall_gap": 0.4})
    wall = f.data.body()
    from scipy.spatial import cKDTree
    # counted by distance, not points: VTK 9.7's clip adds points along the cut edges
    assert cKDTree(wall.points).query(near.points)[0].min() < 0.3
    assert cKDTree(wall.points).query(gap.points)[0].min() >= 0.3  # clip edges interpolate the gap


def test_draws_into_a_plotter():
    layer = make({"level": 0.5, "colour_by": "speed", "range": [0, 1]})
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, frame_for(layer))
    assert len(pl.renderer.actors) >= 1
    pl.close()


def surface_of(spec):
    layer = make({"level": 0.5, **spec})
    f = frame_for(layer)
    mesh = layer.finish(layer.surface(f, f.values), f.values, f)
    return layer, f, mesh


def test_clip_keeps_one_side():
    _, _, below = surface_of({"clip_axis": "z", "clip_position": 0.5, "clip_keep": "below"})
    _, _, above = surface_of({"clip_axis": "z", "clip_position": 0.5, "clip_keep": "above"})
    assert below.points[:, 2].max() <= 0.5 + 1e-9 and above.points[:, 2].min() >= 0.5 - 1e-9
    assert below.n_points and above.n_points


def test_clip_active_false_leaves_whole():
    _, _, whole = surface_of({})
    _, _, off = surface_of({"clip_axis": "z", "clip_position": 0.5, "clip_active": False})
    assert off.n_points == whole.n_points


def test_grow_reveals_along_an_axis():
    _, _, half = surface_of({"grow_axis": "z", "grow": 0.5})
    lo, hi = surface_of({})[2].bounds[4:6]                  # the surface's own extent
    assert half.points[:, 2].max() <= lo + 0.5 * (hi - lo) + 1e-9
    assert half.points[:, 2].max() >= lo + 0.4 * (hi - lo)
    assert surface_of({"grow_axis": "z", "grow": 0})[2].n_points == 0
    _, _, full = surface_of({"grow_axis": "z", "grow": 1})
    assert full.n_points == surface_of({})[2].n_points


def test_grey_blends_to_grey_colour():
    layer, _, _ = surface_of({"grey": 0.5, "grey_colour": "#000000"})
    rgb = np.array([[1.0, 0.5, 0.0]])
    assert layer.grey(rgb, layer.values(0)) == pytest.approx(rgb * 0.5)
    assert make({"level": 0.5}).grey(rgb, make({"level": 0.5}).values(0)) is rgb
