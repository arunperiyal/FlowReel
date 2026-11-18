"""The ``axes`` layer (plan Section 7.2): the solver's directions and the domain's size.

Styles, one per layer:

- ``triad``: three arrows in a small square viewport in a corner of the frame, turning
  with the camera, so it never hides the flow.

Labels are Lato, ``font_size`` pixels high (:func:`flowreel.scene.text.label_at`); like
every size in pixels they shrink with a draft.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from flowreel.scene.layers import Layer, Option, register
from flowreel.scene.text import MARGIN, label_at

STYLES = ("triad",)
CORNERS = ("lower_left", "lower_right", "upper_left", "upper_right")
NAMES = ("x", "y", "z")
COLOURS = ("#e8604c", "#7bc96f", "#5b9bd5")
# Options that belong to one style only; giving one to another style is an error.
ONLY = {"corner": "triad"}


def triad_viewport(corner: str, side: float, picture: tuple[int, int]) -> tuple:
    """The viewport ``(x0, y0, x1, y1)`` (fractions of the picture) of a square ``side``
    pixels in ``corner`` of a picture ``(width, height)``, ``MARGIN`` from its edges."""
    width, height = picture
    pad = MARGIN * height
    x0 = pad if corner.endswith("left") else width - pad - side
    y0 = pad if corner.startswith("lower") else height - pad - side
    return (x0 / width, y0 / height, (x0 + side) / width, (y0 + side) / height)


def triad_renderer(plotter, corner: str, side: float):
    """A renderer drawn over ``plotter``'s, in a square ``side`` pixels in ``corner``,
    with a camera looking at the origin the way the plotter's camera looks at its scene
    (same direction and up, no perspective), a unit arrow reaching about two fifths
    of the way across it."""
    from vtkmodules.vtkRenderingCore import vtkRenderer
    window = plotter.ren_win
    ren = vtkRenderer()
    top = window.GetNumberOfLayers()            # a layer of its own, over pyvista's
    window.SetNumberOfLayers(top + 1)
    ren.SetLayer(top)
    ren.InteractiveOff()
    ren.SetViewport(*triad_viewport(corner, side, tuple(plotter.window_size)))
    window.AddRenderer(ren)
    main = plotter.renderer.GetActiveCamera()
    d = np.asarray(main.GetDirectionOfProjection(), float)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(0, 0, 0)
    cam.SetPosition(*(-5 * d))
    cam.SetViewUp(*main.GetViewUp())
    cam.ParallelProjectionOn()
    cam.SetParallelScale(1.3)
    cam.SetClippingRange(0.1, 10)
    return ren


def _actor(mesh: pv.PolyData, colour, opacity: float, ambient: float = 0.35):
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

    from flowreel.tracks import parse_colour
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*(parse_colour(colour) if isinstance(colour, str) else colour))
    prop.SetOpacity(opacity)
    prop.SetAmbient(ambient)
    prop.SetDiffuse(1 - ambient)
    return actor


def _arrow(start, direction, length: float, bold: float = 1.0) -> pv.PolyData:
    """An arrow ``length`` long; ``bold`` scales its thickness."""
    return pv.Arrow(start=start, direction=direction, scale=length, tip_length=0.22,
                    tip_radius=0.07 * bold, shaft_radius=0.025 * bold, tip_resolution=24,
                    shaft_resolution=24)


@register
class Axes(Layer):
    """Axes in a shot: ``style`` ``triad`` (see the module).

    Options for every style: ``axes`` (which, default ``[x, y, z]``), ``labels`` (their
    names, default the axes'), ``colours`` (one per axis, for the arrows), ``colour``
    (text and lines), ``opacity``, ``font_size`` (pixels) and ``width`` (lines, pixels).
    ``triad``: ``corner`` and ``size`` (the square's side, pixels).
    """

    name = "axes"
    options = (
        Option("style", track=False, default="triad", doc="triad"),
        Option("axes", track=False, default=None, doc="which axes; default [x, y, z]"),
        Option("labels", track=False, default=None, doc="names of the axes; default x, y, z"),
        Option("colours", track=False, default=None, doc="arrow colour per axis"),
        Option("colour", "colour", default="#d0d4d8", doc="text and lines"),
        Option("opacity", "number", default=1.0),
        Option("font_size", "number", default=18.0, pixels=True, doc="label height, pixels"),
        Option("width", "number", default=1.5, pixels=True, doc="line width, pixels"),
        Option("corner", track=False, default=None, doc="triad: lower_left ..."),
        Option("size", "number", default=110.0, pixels=True, doc="triad: side, pixels"),
    )

    @classmethod
    def check(cls, raw: dict, check) -> None:
        style = check.at("style").choice(raw.get("style", "triad"), STYLES)
        for key, owner in ONLY.items():
            if raw.get(key) is not None and owner != style:
                raise check.at(key).error(f"is an option of style {owner}, not {style}")
        axes = raw.get("axes")
        if axes is None:
            raw["axes"] = list(NAMES)
        else:
            items = check.at("axes").sequence(axes, 1)
            for i, a in enumerate(items):
                check.at("axes", i).choice(a, NAMES)
            if len(set(items)) != len(items):
                raise check.at("axes").error(f"names an axis twice: {items}")
        n = len(raw["axes"])
        labels = raw.get("labels")
        if labels is not None:
            items = check.at("labels").sequence(labels)
            if len(items) != n:
                raise check.at("labels").error(f"expected {n} labels, one per axis, got {len(items)}")
            for i, s in enumerate(items):
                check.at("labels", i).string(s)
        colours = raw.get("colours")
        if colours is not None:
            from flowreel.tracks import parse_colour
            items = check.at("colours").sequence(colours)
            if len(items) != n:
                raise check.at("colours").error(f"expected {n} colours, one per axis, got {len(items)}")
            for i, c in enumerate(items):
                try:
                    parse_colour(c)
                except ValueError as exc:
                    raise check.at("colours", i).wrap(exc) from None
        if style == "triad":
            raw["corner"] = check.at("corner").choice(raw.get("corner") or "lower_left", CORNERS)

    # -- what each style draws, for the layer and its tests -------------------------

    def _axes(self, v) -> list[tuple[int, str, str]]:
        """``(index, label, colour)`` of each axis drawn."""
        names = v["axes"]
        labels = v.get("labels") or names
        colours = v.get("colours") or [COLOURS[NAMES.index(a)] for a in names]
        return [(NAMES.index(a), str(lab), c) for a, lab, c in zip(names, labels, colours)]

    def draw(self, plotter, frame) -> None:
        v = frame.values
        getattr(self, "_" + v["style"])(plotter, frame, v)

    def _triad(self, plotter, frame, v) -> None:
        ren = triad_renderer(plotter, v["corner"], v["size"])
        for k, label, colour in self._axes(v):
            e = np.eye(3)[k]
            ren.AddActor(_actor(_arrow((0, 0, 0), e, 1.0, bold=1.6), colour, v["opacity"]))
            label_at(ren, label, 1.22 * e, v["font_size"], v["colour"], v["opacity"])


