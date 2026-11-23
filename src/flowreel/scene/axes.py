"""The ``axes`` layer (plan Section 7.2): the solver's directions and the domain's size.

Three styles, one per layer; a shot may use any of them:

- ``triad``: three arrows in a small square viewport in a corner of the frame, turning
  with the camera, so it never hides the flow.
- ``arrows``: labelled arrows in the scene at ``origin``, a point or a body's end,
  ``length`` long in model units or in diameters.
- ``ruled``: a box (``domain``, ``crop`` or numbers) with ticks and numbers along one
  edge in each direction, the edge the camera sees on the outside of the box, in the
  source's unit or in diameters.

Labels are Lato, ``font_size`` pixels high (:func:`flowreel.scene.text.label_at`); like
every size in pixels they shrink with a draft.
"""
from __future__ import annotations

import math

import numpy as np
import pyvista as pv

from flowreel.box import Box
from flowreel.scene.drawn import keep_shape, scale_of
from flowreel.scene.layers import Layer, Option, register
from flowreel.scene.marker_layers import _check_region, region
from flowreel.scene.text import MARGIN, label_at, to_display

STYLES = ("triad", "arrows", "ruled")
CORNERS = ("lower_left", "lower_right", "upper_left", "upper_right")
NAMES = ("x", "y", "z")
COLOURS = ("#e8604c", "#7bc96f", "#5b9bd5")
UNITS = ("model", "diameters")
# Options that belong to one style only; giving one to another style is an error.
ONLY = {"corner": "triad", "origin": "arrows", "bounds": "ruled", "ticks": "ruled"}


def nice_step(span: float, count: int = 5) -> float:
    """A round tick spacing (1, 2 or 5 times a power of ten) giving about ``count``
    intervals over ``span``."""
    if not span > 0:
        raise ValueError(f"span must be positive, got {span:g}")
    raw = span / count
    power = 10 ** math.floor(math.log10(raw))
    return min((m * power for m in (1, 2, 5, 10)), key=lambda s: abs(math.log(s / raw)))


def ticks(lo: float, hi: float, step: float | None = None) -> np.ndarray:
    """Multiples of ``step`` (default :func:`nice_step`) from ``lo`` to ``hi``,
    both ends included when they fall on one."""
    step = step or nice_step(hi - lo)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    return np.round(np.arange(first, last + 1) * step, 12)


def tick_text(value: float) -> str:
    """A tick's number: no trailing zeros, ``-0`` written ``0``."""
    return f"{value:g}" if value != 0 else "0"


def outer_edges(renderer, box: Box) -> list[tuple[np.ndarray, np.ndarray]]:
    """For each axis, the edge of ``box`` to rule: of its four edges along that axis, the
    one whose middle falls furthest from the box's middle in ``renderer``'s view (the
    lower one on a tie). Returns ``(fixed, outward)`` per axis: the edge's two other
    coordinates as a point with the axis' coordinate 0, and the unit vector from the
    box's middle out to the edge, across the axis."""
    lo, hi = np.asarray(box.lo, float), np.asarray(box.hi, float)
    mid = (lo + hi) / 2
    cx, cy, _ = to_display(renderer, mid)
    out = []
    for k in range(3):
        i, j = [a for a in range(3) if a != k]
        best = None
        for si in (lo[i], hi[i]):
            for sj in (lo[j], hi[j]):
                p = mid.copy()
                p[i], p[j] = si, sj
                x, y, _ = to_display(renderer, p)
                score = (round(math.hypot(x - cx, y - cy), 3), -y)
                if best is None or score > best[0]:
                    fixed = np.zeros(3)
                    fixed[i], fixed[j] = si, sj
                    outward = np.zeros(3)
                    outward[i] = np.sign(si - mid[i]) / math.sqrt(2)
                    outward[j] = np.sign(sj - mid[j]) / math.sqrt(2)
                    best = (score, fixed, outward)
        out.append((best[1], best[2]))
    return out


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
    """Axes in a shot: ``style`` ``triad``, ``arrows`` or ``ruled`` (see the module).

    Options for every style: ``axes`` (which, default ``[x, y, z]``), ``labels`` (their
    names, default the axes'), ``colours`` (one per axis, for the arrows), ``colour``
    (text and lines), ``opacity``, ``font_size`` (pixels) and ``width`` (lines, pixels).
    ``triad``: ``corner`` and ``size`` (the square's side, pixels). ``arrows``:
    ``origin`` (``[x, y, z]`` or ``{body: NAME, end: 0 | 1}``, the low or high end
    along the body's axis), ``length`` and ``unit``. ``ruled``: ``bounds``, ``ticks``
    (spacing in the unit shown, or ``auto``) and ``unit``. ``unit: diameters`` divides
    lengths by ``body``'s diameter (declared, else measured).
    """

    name = "axes"
    options = (
        Option("style", track=False, default="triad", doc="triad, arrows or ruled"),
        Option("axes", track=False, default=None, doc="which axes; default [x, y, z]"),
        Option("labels", track=False, default=None, doc="names of the axes; default x, y, z"),
        Option("colours", track=False, default=None, doc="arrow colour per axis"),
        Option("colour", "colour", default="#d0d4d8", doc="text and lines"),
        Option("opacity", "number", default=1.0),
        Option("font_size", "number", default=18.0, pixels=True, doc="label height"),
        Option("width", "number", default=1.5, pixels=True, doc="line width, ruled"),
        Option("corner", track=False, default=None, doc="triad: lower_left ..."),
        Option("size", "number", default=110.0, pixels=True, doc="triad: side of its square"),
        Option("origin", track=False, default=None,
               doc="arrows: [x, y, z] or {body: NAME, end: 0 | 1}", example=[0, 0, 0]),
        Option("length", "number", default=1.0, doc="arrows: length, in unit"),
        Option("unit", track=False, default="model", doc="model or diameters"),
        Option("body", track=False, default=None, doc="the body whose diameter is the unit"),
        Option("bounds", track=False, default=None, doc="ruled: domain, crop or numbers"),
        Option("ticks", track=False, default=None, doc="ruled: spacing in unit, or auto"),
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
        check.at("unit").choice(raw.get("unit", "model"), UNITS)
        if raw.get("body") is not None:
            check.at("body").string(raw["body"])
        if style == "triad":
            raw["corner"] = check.at("corner").choice(raw.get("corner") or "lower_left", CORNERS)
            if raw.get("unit", "model") != "model":
                raise check.at("unit").error("a triad shows directions, not lengths")
        if style == "arrows":
            if raw.get("origin") is None:
                raise check.error("missing key 'origin' (a point [x, y, z] or {body: NAME, end: 0})")
            _check_origin(raw["origin"], check.at("origin"))
        if style == "ruled":
            raw["bounds"] = raw.get("bounds") or "domain"
            _check_region(raw["bounds"], check.at("bounds"))
            t = raw.get("ticks") or "auto"
            if t != "auto" and check.at("ticks").number(t) <= 0:
                raise check.at("ticks").error(f"must be positive, got {t}")
            raw["ticks"] = t

    # -- what each style draws, for the layer and its tests -------------------------

    def _axes(self, v) -> list[tuple[int, str, str]]:
        """``(index, label, colour)`` of each axis drawn."""
        names = v["axes"]
        labels = v.get("labels") or names
        colours = v.get("colours") or [COLOURS[NAMES.index(a)] for a in names]
        return [(NAMES.index(a), str(lab), c) for a, lab, c in zip(names, labels, colours)]

    def diameter(self, data, origin_body: str | None = None) -> float:
        """The unit length: 1, or the diameter of ``body``; with no ``body`` named, the
        project's ``reference: {length}`` when given, else the diameter of
        ``origin_body`` (arrows at a body's end) or of the one body."""
        if self.raw.get("unit", "model") == "model":
            return 1.0
        if not self.raw.get("body") and data.reference.get("length"):
            return float(data.reference["length"])
        from flowreel.project.measure import diameter
        from flowreel.project.names import declaration, one_body
        name = self.raw.get("body") or origin_body or one_body(data.source)
        decl = declaration(data.source, name)
        if decl is not None and decl.diameter:
            return float(decl.diameter)
        return float(diameter(data.body(name), decl.axis if decl else None))

    def origin(self, data) -> tuple[np.ndarray, str | None]:
        """The arrows' start and the body it is on (``None`` for a point)."""
        spec = self.raw["origin"]
        if not isinstance(spec, dict):
            return np.asarray(spec, float), None
        from flowreel.project.measure import AXES, centre, long_axis
        from flowreel.project.names import declaration, one_body
        name = spec.get("body") or one_body(data.source)
        surface = data.body(name)
        decl = declaration(data.source, name)
        axis = (decl.axis if decl else None) or long_axis(surface)
        if axis is None:
            raise ValueError(f"axes: body {name!r} is not slender; declare its 'axis' or "
                             "give origin as a point")
        span = np.asarray(surface.points)[:, AXES[axis]]
        station = span.max() if spec.get("end", 0) else span.min()
        slab = 0.25 * decl.diameter if decl and decl.diameter else None
        return np.asarray(centre(surface, station, axis, slab), float), name

    def draw(self, plotter, frame) -> None:
        v = frame.values
        getattr(self, "_" + v["style"])(plotter, frame, v)

    def _triad(self, plotter, frame, v) -> None:
        ren = triad_renderer(plotter, v["corner"], v["size"])
        for k, label, colour in self._axes(v):
            e = np.eye(3)[k]
            ren.AddActor(_actor(_arrow((0, 0, 0), e, 1.0, bold=1.6), colour, v["opacity"]))
            label_at(ren, label, 1.22 * e, v["font_size"], v["colour"], v["opacity"])

    def _arrows(self, plotter, frame, v) -> None:
        start, body = self.origin(frame.data)
        length = v["length"] * self.diameter(frame.data, body)
        ren = plotter.renderer
        scale = scale_of(ren)                 # a stretch must not bend the arrows
        for k, label, colour in self._axes(v):
            e = np.eye(3)[k]
            arrow = keep_shape(ren, _arrow(start, e, length), start)
            ren.AddActor(_actor(arrow, colour, v["opacity"]))
            label_at(ren, label, start + 1.15 * length * e / scale, v["font_size"],
                     v["colour"], v["opacity"])

    def rulings(self, plotter, frame, v=None) -> list[dict]:
        """What the ``ruled`` style draws along each axis: ``axis`` (index), ``edge``
        (``fixed``, ``outward`` from :func:`outer_edges`), ``ticks`` (model positions
        along the axis) and ``text`` (their numbers, in the unit shown).

        Numbers must not run into each other: an axis whose edge is shorter in the
        frame than two labels (one that points at the camera) is not ruled, ``auto``
        ticks are spaced at least two labels apart in the frame, and an axis left with
        fewer than two ticks is not ruled.
        """
        v = v or frame.values
        box = region(v["bounds"], frame.data)
        unit = self.diameter(frame.data)
        edges = outer_edges(plotter.renderer, box)
        room = 2 * v["font_size"]
        out = []
        for k, label, _ in self._axes(v):
            fixed = edges[k][0]
            a, b = fixed.copy(), fixed.copy()
            a[k], b[k] = box.lo[k], box.hi[k]
            pixels = float(np.hypot(*np.subtract(to_display(plotter.renderer, b)[:2],
                                                 to_display(plotter.renderer, a)[:2])))
            if pixels < room:
                continue
            lo, hi = box.lo[k] / unit, box.hi[k] / unit
            if v["ticks"] == "auto":
                step = nice_step(hi - lo)
                while step * pixels / (hi - lo) < room:
                    step = nice_step(2.2 * step, 1)          # the next round step up
            else:
                step = float(v["ticks"])
            values = ticks(lo, hi, step)
            if len(values) < 2:                       # one number is no scale
                continue
            out.append({"axis": k, "label": label, "edge": edges[k],
                        "ticks": values * unit, "text": [tick_text(t) for t in values]})
        return out

    def _ruled(self, plotter, frame, v) -> None:
        box = region(v["bounds"], frame.data)
        lo, hi = np.asarray(box.lo, float), np.asarray(box.hi, float)
        ren = plotter.renderer
        scale = scale_of(ren)         # ticks and offsets are lengths as drawn
        reach = 0.025 * float(np.max((hi - lo) * scale))
        lines = [pv.Box(bounds=box.to_bounds()).extract_all_edges()]
        diameters = self.raw.get("unit") == "diameters"
        for rule in self.rulings(plotter, frame, v):
            k = rule["axis"]
            fixed, outward = rule["edge"]
            for t, text in zip(rule["ticks"], rule["text"]):
                p = fixed.copy()
                p[k] = t
                lines.append(keep_shape(ren, pv.Line(p, p + reach * outward), p))
                label_at(ren, text, p + 2.6 * reach * outward / scale,
                         v["font_size"], v["colour"], v["opacity"])
            middle = fixed.copy()
            middle[k] = (lo[k] + hi[k]) / 2
            title = rule["label"] + (" / D" if diameters else "")
            label_at(ren, title, middle + 5.5 * reach * outward / scale,
                     v["font_size"], v["colour"], v["opacity"])
        plotter.add_mesh(pv.merge(lines), color=v["colour"], line_width=v["width"],
                         opacity=v["opacity"], lighting=False)


def _check_origin(spec, check) -> None:
    if isinstance(spec, dict):
        m = check.mapping(spec, ("body", "end"))
        if m.get("body") is not None:
            check.at("body").string(m["body"])
        if m.get("end", 0) not in (0, 1):
            raise check.at("end").error(f"expected 0 (the low end) or 1 (the high end), got {m['end']!r}")
        return
    check.numbers(spec, 3)
