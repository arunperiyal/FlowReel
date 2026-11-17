"""Draw one frame of a shot into a picture (the smallest render path).

``draw_frame`` reads the data a frame needs, builds a plotter, lets each layer draw and
returns the picture. Process pools, frame keys and caches come with the render branch,
which builds on this.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv

from flowreel.scene import flow_layers as _flow_layers  # noqa: F401  (registers layers)
from flowreel.scene.errors import Checker
from flowreel.scene.layers import Frame, FrameData
from flowreel.scene.plan import plan
from flowreel.scene.shot import Shot
from flowreel.scene.views import View, load_views
from flowreel.tracks import parse_colour

FLOW_FIELDS = ["U", "V", "W"]


def find_view(shot: Shot, views: dict[str, View] | None = None) -> View:
    """The shot's view: ``camera: {view: name}``, looked up in ``views`` or in the
    ``cameras.yml`` next to the shot file."""
    name = shot.camera.get("view")
    if name is None:
        raise Checker(shot.file, ("camera",)).error("draw needs 'view' (tracks and framing "
                                                    "come with the render branch)")
    if views is None:
        if not shot.file:
            raise Checker(shot.file, ("camera",)).error("no cameras.yml to read the view from")
        views = load_views(Path(shot.file).parent / "cameras.yml")
    check = Checker(shot.file, ("camera", "view"))
    return views[check.choice(name, list(views))]


def draw_frame(shot: Shot, source, index: int, views: dict[str, View] | None = None,
               size: tuple[int, int] | None = None) -> np.ndarray:
    """Draw frame ``index`` of ``shot`` from ``source``; ``(height, width, 3)`` uint8.

    ``views`` are the named views (default: ``cameras.yml`` beside the shot file);
    ``size`` overrides the shot's size.
    """
    fp = plan(shot, source)
    frame = fp.frame(index)
    flow = None
    if any(layer.needs_flow for layer in shot.layers):
        flow = source.flow(frame.step, FLOW_FIELDS, shot.crop)
    data = FrameData(source, frame.step, flow)
    view = find_view(shot, views)
    plotter = pv.Plotter(off_screen=True, window_size=list(size or shot.size))
    try:
        plotter.set_background(_background(shot.background))
        view.apply(plotter.camera)
        if shot.antialias != "none":
            plotter.enable_anti_aliasing(shot.antialias)
        for layer, values in zip(shot.layers, frame.values):
            layer.draw(plotter, Frame(frame.index, frame.step, frame.time, data, values))
        return np.asarray(plotter.screenshot(return_img=True))[:, :, :3]
    finally:
        plotter.close()


def _background(value):
    return tuple(parse_colour(value)) if isinstance(value, str) and value.startswith("#") \
        else value
