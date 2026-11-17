import numpy as np
import pytest
import pyvista as pv

import flowreel.scene.flow_layers  # noqa: F401
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker
from tests.conftest import ToySource


class TwoBodies(ToySource):
    def bodies(self):
        return ["a", "b"]

    def body(self, step, name=None):
        a = pv.Sphere(radius=0.2, center=(0, 0, 0.5))
        b = pv.Sphere(radius=0.1, center=(0.5, 0, 0.5))
        return {"a": a, "b": b}.get(name) or a.merge(b)


def make(**spec):
    return L.build({"type": "body", **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, flow=True, src=None):
    src = src or TwoBodies()
    grid = src.flow(0, ["U", "V", "W"], None) if flow else None
    return L.Frame(0, 0, 0.0, L.FrameData(src, 0, grid), layer.values(0))


def test_selects_one_a_list_or_all():
    n = {k: make(**({"body": k} if k else {})).surface(frame_for(make())).n_points
         for k in ("a", "b", "all", None)}
    assert n["all"] == n["a"] + n["b"] == n[None]
    both = make(body=["a", "b"]).surface(frame_for(make()))
    assert both.n_points == n["all"]


def test_field_from_the_flow_is_sampled_onto_the_body():
    layer = make(body="a", field="speed")
    surf = layer.surface(frame_for(layer))
    r = np.hypot(surf.points[:, 0], surf.points[:, 1])
    assert np.asarray(surf["speed"]) == pytest.approx(r, abs=0.06)    # speed = omega * r


def test_field_needs_the_flow():
    layer = make(field="speed")
    with pytest.raises(ValueError, match="needs the flow"):
        layer.surface(frame_for(layer, flow=False))


def test_ghost_is_see_through_and_draws():
    for spec in ({}, {"style": "ghost"}, {"field": "speed", "zero_contour": True, "range": [0, 1]}):
        layer = make(**spec)
        pl = pv.Plotter(off_screen=True)
        layer.draw(pl, frame_for(layer))
        assert pl.renderer.actors
        pl.close()
    layer = make(style="ghost", opacity=0.9)
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, frame_for(layer))
    assert list(pl.renderer.actors.values())[0].GetProperty().GetOpacity() == pytest.approx(0.3)
    pl.close()


def test_rejects_bad_style():
    from flowreel.scene.errors import ConfigError
    with pytest.raises(ConfigError, match="did you mean 'ghost'"):
        make(style="ghots")
