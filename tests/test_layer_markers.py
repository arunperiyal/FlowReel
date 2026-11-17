import numpy as np
import pytest
import pyvista as pv

import flowreel.scene.marker_layers  # noqa: F401
from flowreel.box import Box
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker, ConfigError
from tests.conftest import ToySource


def make(kind, **spec):
    return L.build({"type": kind, **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, crop=None, flow=False, src=None):
    src = src or ToySource()
    grid = src.flow(0, ["U", "V", "W"], None) if flow else None
    return L.Frame(0, 0, 0.0, L.FrameData(src, 0, grid, crop), layer.values(0))


def actors_of(layer, **kw):
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, frame_for(layer, **kw))
    out = list(pl.renderer.actors.values())
    pl.close()
    return out


def bounds_of(actor):
    return actor.GetMapper().GetInput().GetBounds()


def test_outline_domain_crop_and_numbers():
    dom = actors_of(make("outline"))[0]
    assert bounds_of(dom) == pytest.approx((-1, 1, -1, 1, 0, 1))
    crop = Box((0, 0, 0), (0.5, 0.5, 0.5))
    assert bounds_of(actors_of(make("outline", bounds="crop"), crop=crop)[0]) == pytest.approx((0, .5, 0, .5, 0, .5))
    assert bounds_of(actors_of(make("outline", bounds="crop"))[0]) == pytest.approx((-1, 1, -1, 1, 0, 1))
    num = make("outline", bounds={"x": [0, 1], "y": [0, 2], "z": [0, 3]})
    assert bounds_of(actors_of(num)[0]) == pytest.approx((0, 1, 0, 2, 0, 3))


def test_outline_width_opacity_tracks_and_errors():
    layer = make("outline", opacity={"from": 0, "to": 1, "frames": [0, 10], "ease": "linear"}, width=3)
    assert layer.values(5)["opacity"] == pytest.approx(0.5)
    a = actors_of(layer)[0]
    assert a.GetProperty().GetLineWidth() == 3 and a.GetProperty().GetOpacity() == 0
    with pytest.raises(ConfigError, match="bounds: 'domian' is not allowed"):
        make("outline", bounds="domian")
    with pytest.raises(ConfigError, match=r"bounds.x: expected \[low, high\]"):
        make("outline", bounds={"x": [1, 0], "y": [0, 1], "z": [0, 1]})
