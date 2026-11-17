import numpy as np
import pytest
import pyvista as pv

import flowreel.scene.flow_layers  # noqa: F401
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker
from tests.conftest import ToySource


def make(**spec):
    base = {"type": "slice", "normal": "z", "position": 0.5, "field": "speed", "range": [0, 1]}
    return L.build({**base, **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, index=0):
    src = ToySource()
    return L.Frame(index, 0, 0.0, L.FrameData(src, 0, src.flow(0, ["U", "V", "W"], None)),
                   layer.values(index))


def rgba_of(**spec):
    layer = make(**spec)
    f = frame_for(layer)
    return layer.mesh(f, f.values)


def test_section_lies_in_the_plane_with_colours():
    cut = rgba_of()
    assert np.allclose(cut.points[:, 2], 0.5) and cut["rgba"].dtype == np.uint8
    assert (cut["rgba"][:, 3] == 255).all()


def test_position_is_a_track():
    layer = make(position={"from": 0.2, "to": 0.8, "frames": [0, 10], "ease": "linear"})
    assert layer.values(5)["position"] == pytest.approx(0.5)


def test_fade_weak_makes_weak_values_transparent():
    cut = rgba_of(fade_weak=[0.1, 0.5])
    speed, alpha = np.asarray(cut["speed"]), cut["rgba"][:, 3]
    assert (alpha[speed <= 0.1] == 0).all() and (alpha[speed >= 0.5] == 255).all()
    assert 0 < alpha[(speed > 0.2) & (speed < 0.4)].min() < 255


def test_near_wall_masks_the_body():
    cut = rgba_of(near_wall=[0.05, 0.3])
    d = np.linalg.norm(cut.points - (0, 0, 0.5), axis=1) - 0.2
    alpha = cut["rgba"][:, 3]
    assert alpha[np.abs(d) < 0.06].min() < 255 and alpha[d > 0.4].min() == 255


def test_opacity_scales_alpha_and_empty_plane_is_none():
    assert (rgba_of(opacity=0.5)["rgba"][:, 3] == 128).all()
    assert rgba_of(position=9.0) is None


def test_draws():
    layer = make()
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, frame_for(layer))
    assert len(pl.renderer.actors) >= 1
    pl.close()
