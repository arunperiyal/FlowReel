"""Panels drawn from flow data (plan Section 9.2): ``section``, ``cuts`` and ``strip``.

Each frame shows the saved step nearest the frame's time (flow is never interpolated
between steps). The data come from a source, named as a shot names one; without
``source``, a panel whose ``times`` are a shot's (``times: {shot: FILE}``) reads that
shot's source. Body names are those of the project's ``flowreel.yml``.

**section.** A cut across a body at a station: a field as filled contours, the
streamlines of the flow seen from the moving body, the body's outline, and an inset, a
close view that follows the body, with its box drawn on the main view.

.. code-block:: yaml

    type: section
    size: [1920, 1080]
    times: {shot: travel.yml}
    body: riser
    station: 250
    field: vorticity_x
    range: [-3, 3]
    half: 1.5
    inset: {offset: [0.3, 0.4], half: 0.3}

**cuts.** The same cut at several stations side by side, each labelled, so the phase of
shedding can be read along the span. Each view follows the body at its station, or
stays at ``centre``.

.. code-block:: yaml

    type: cuts
    size: [1920, 540]
    times: {shot: travel.yml}
    body: riser
    stations: [125, 250, 375]
    field: vorticity_x
    range: [-2.5, 2.5]
    centre: [3.5, 0]
    half: [5, 4.2]
    label: 'x = {station:g} D'

**strip.** A body seen from one side (``side``: the axis the eye is on, signed), its
span across, coloured by a wall field, with the line where the field is zero, such as
where the flow leaves the wall. The picture is a true view, not mirrored.

.. code-block:: yaml

    type: strip
    size: [1920, 540]
    times: {shot: travel.yml}
    body: riser
    side: y
    field: skin_friction
    component: z
    params: {rho: 1, u_inf: 1, mu: 0.0001}
    range: [-0.03, 0.03]
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from flowreel.box import Box
from flowreel.compose import flow_cut as fc
from flowreel.compose.panels import PanelType, register
from flowreel.compose.style import colour
from flowreel.scene.errors import Checker, ConfigError

BODY_COLOUR = "#c8ccd0"


def open_panel_source(panel, value, check: Checker):
    """The source a flow panel reads, seen through the project's bodies: ``value`` (a
    shot's ``source``, paths from the panel file's folder), else the source of the shot
    whose times the panel takes. Returns ``(source, id, project)``: ``id`` is the source
    as keys take it (paths resolved), ``project`` the panel's project or ``None``."""
    from flowreel import sources
    from flowreel.project import project_for
    from flowreel.project.names import declare
    from flowreel.scene.rendering import source_id, source_options
    from flowreel.scene.shot import _source
    if value is not None:
        (adapter, location), options = _source(value, check.at("source"))
        holder = SimpleNamespace(source=(adapter, location), source_options=options,
                                 file=str(panel.file) if panel.file else None)
    elif isinstance(panel.times, Path):
        from flowreel.compose.stations import read_shot
        holder = read_shot(panel.times, check.at("times", "shot"))
    else:
        raise check.error("missing key 'source' (the flow to read); or take the times and "
                          "the source of a shot with 'times: {shot: FILE}'")
    where = check.at("source") if value is not None else check.at("times", "shot")
    try:
        source = sources.create(holder.source[0], **source_options(holder))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise where.error(f"cannot open the source: {exc}") from None
    project = project_for(panel.file) if panel.file else None
    return declare(source, project), source_id(holder), project


def available_fields() -> set[str]:
    """The names of the derived fields (a source's own arrays take no parameters)."""
    from flowreel.fields.registry import available
    return set(available())


class FlowPanel(PanelType):
    """The keys every flow panel has: where the flow is, the body, the field and its
    colours. Subclasses add their own and draw."""

    COMMON = ("source", "body", "field", "params", "range", "colormap", "levels", "view")
    VIEW = (0.02, 0.02, 0.96, 0.96)

    def parse(self, options, check):
        from flowreel.colours import colormap
        from flowreel.project.names import one_body
        self.source, self.source_id, self.project = open_panel_source(
            self.panel, options.get("source"), check)
        try:
            self.body = (check.at("body").string(options["body"]) if options.get("body")
                         else one_body(self.source))
            self.source.body(self.source.steps()[0], self.body)
        except (LookupError, ValueError) as exc:
            message = exc.args[0] if exc.args else str(exc)
            raise check.at("body").error(str(message)) from None
        if "field" not in options:
            raise check.error("missing key 'field' (the field to draw)")
        self.field = check.at("field").string(options["field"])
        self._check_field(self.field, check.at("field"))
        params = options.get("params") or {}
        if not isinstance(params, dict):
            raise check.at("params").error(f"expected a mapping of numbers, got {params!r}")
        given = {k: check.at("params", k).number(v) for k, v in params.items()}
        # the project's reference values the field takes; the panel's own win
        from flowreel.fields.registry import accepted
        reference = self.project.reference if self.project is not None else {}
        wanted = accepted([self.field]) if self.field in available_fields() else set()
        self.params = {**{k: v for k, v in reference.items() if k in wanted}, **given}
        if options.get("range") is None:
            raise check.error("missing key 'range' ([low, high] of the colour map; a range "
                              "taken from each frame's data would change from frame to frame)")
        lo, hi = check.at("range").numbers(options["range"], 2)
        if lo >= hi:
            raise check.at("range").error(f"expected [low, high] with low < high, got "
                                          f"[{lo:g}, {hi:g}]")
        self.range = (lo, hi)
        name = options.get("colormap", "fire_ice")
        try:
            colormap(check.at("colormap").string(name))
        except ValueError as exc:
            raise check.at("colormap").wrap(exc) from None
        self.colormap = name
        self.levels = check.at("levels").integer(options.get("levels", 41), minimum=2)
        self.view = self._rect(options.get("view"), check.at("view"), self.VIEW)
        self._steps = sorted((float(self.source.time(s)), s) for s in self.source.steps())

    def _check_field(self, name: str, check: Checker) -> None:
        from flowreel.fields.registry import available
        known = set(self.source.fields()) | set(available())
        if name not in known:
            raise check.error(f"no field {name!r}: the source provides "
                              f"{', '.join(sorted(self.source.fields()))}, and the derived "
                              f"fields are {', '.join(available())}")

    @staticmethod
    def _rect(value, check: Checker, default) -> tuple[float, float, float, float]:
        """``[left, bottom, width, height]`` as shares of the figure."""
        if value is None:
            return tuple(default)
        rect = check.numbers(value, 4)
        if min(rect) < 0 or rect[2] <= 0 or rect[3] <= 0 or rect[0] + rect[2] > 1 + 1e-9 \
                or rect[1] + rect[3] > 1 + 1e-9:
            raise check.error("expected [left, bottom, width, height] inside the figure, "
                              f"got {list(rect)}")
        return rect

    def declared(self):
        """The body's declaration, or ``None``."""
        from flowreel.project.names import declaration
        return declaration(self.source, self.body)

    def files(self):
        out = []
        for step in self.source.steps():
            out += [Path(f) for f in getattr(self.source, "files", lambda s: [])(step)]
        if self.project is not None and self.project.file is not None:
            out.append(self.project.file)
        return out

    def settings(self):
        return {"options": self.panel.options, "source": self.source_id}

    def step_at(self, time: float) -> int:
        """The saved step whose time is nearest ``time`` (the earlier one at a tie)."""
        times = [t for t, _ in self._steps]
        i = int(np.searchsorted(times, time))
        if i == 0:
            return self._steps[0][1]
        if i == len(times):
            return self._steps[-1][1]
        (ta, a), (tb, b) = self._steps[i - 1], self._steps[i]
        return a if time - ta <= tb - time else b

    def failed(self, time: float, exc: Exception) -> ConfigError:
        """An error of the frame at ``time``, naming the panel file."""
        message = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
        return Checker(self.panel.file).error(f"the frame at time {time:g}: {message}")

    def contours(self, ax, tri, values) -> None:
        """``values`` on ``tri`` as filled contours in the panel's colours."""
        from flowreel.colours import colormap
        lo, hi = self.range
        ax.tricontourf(tri, np.clip(values, lo, hi), levels=np.linspace(lo, hi, self.levels),
                       cmap=colormap(self.colormap), extend="neither")


def bare(ax, style) -> None:
    """An axes with nothing but its picture: no ticks, no edges."""
    ax.set_facecolor(style.background)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


class CutPanel(FlowPanel):
    """A flow panel of cuts across its body: the body's axis, the station, the view
    round the body and the slab read."""

    CUT = ("axes", "depth", "half", "centre", "body_colour")

    def parse(self, options, check):
        from flowreel.project.measure import diameter, long_axis
        super().parse(options, check)
        decl = self.declared()
        surface = self.source.body(self.source.steps()[0], self.body)
        self.axis = (decl.axis if decl else None) or long_axis(surface)
        if self.axis is None:
            raise check.at("body").error(f"body {self.body!r} is not slender, so it has no "
                                         "stations; declare its 'axis' in flowreel.yml")
        self.diameter = (decl.diameter if decl and decl.diameter else None) or \
            diameter(surface, self.axis)
        self.slab = 0.25 * self.diameter
        normal = fc.AXES.index(self.axis)
        try:
            self.axes = fc.plane_axes(normal, options.get("axes"))
        except ValueError as exc:
            raise check.at("axes").wrap(exc) from None
        self.depth = check.at("depth").number(options.get("depth", self.diameter))
        if self.depth <= 0:
            raise check.at("depth").error(f"must be positive, got {self.depth:g}")
        self.half = self._half(options.get("half", 1.5 * self.diameter), check.at("half"))
        self.centre = None if options.get("centre") is None else \
            np.asarray(check.at("centre").numbers(options["centre"], 2))
        self.body_colour = colour(options.get("body_colour", BODY_COLOUR), check.at("body_colour"))

    @staticmethod
    def _half(value, check: Checker) -> np.ndarray:
        """Half-sizes ``(across, up)`` of a view: one number or two."""
        half = (check.number(value),) * 2 if not isinstance(value, (list, tuple)) else \
            check.numbers(value, 2)
        if min(half) <= 0:
            raise check.error(f"must be positive, got {list(half)}")
        return np.asarray(half, dtype=float)

    def body_centre(self, step: int, station: float) -> np.ndarray:
        """The body's centre at ``station`` in the plane's ``(across, up)``."""
        c = fc.body_centre(self.source, step, self.body, self.axis, station, self.slab)
        return c[list(self.axes)]

    def read(self, step: int, station: float, boxes: list[tuple[np.ndarray, np.ndarray]]):
        """The cut at ``station`` of ``step``, read in a slab round the views ``boxes``
        (``(lo, hi)`` pairs in the plane) grown by ``depth`` (a cell crossing the box's
        edge is not read), and the outlines of every wall body there."""
        plane = fc.station_plane(self.axis, station)
        lo = np.min([b[0] for b in boxes], axis=0)
        hi = np.max([b[1] for b in boxes], axis=0)
        grow = 0.05 * (hi - lo) + self.depth      # cells cut by the box's edge are lost
        crop = fc.plane_box(plane, self.axes, lo - grow, hi + grow, self.depth)
        cut = fc.read_cut(self.source, step, plane, [self.field], crop, self.axes, self.params)
        curves = fc.outlines(self.source.body(step, None), plane, self.axes)
        return cut, curves, crop

    def draw_cut(self, ax, cut, curves, centre, half) -> None:
        """A cut on ``ax``: contours, the body filled, the view ``centre`` ± ``half``."""
        self.contours(ax, cut.triangulation(), cut.values[self.field])
        for c in curves:
            ax.fill(c[:, 0], c[:, 1], color=self.body_colour, zorder=3, linewidth=0)
        ax.set_xlim(centre[0] - half[0], centre[0] + half[0])
        ax.set_ylim(centre[1] - half[1], centre[1] + half[1])
        ax.set_aspect("equal")


@register
class SectionPanel(CutPanel):
    """A cut across a body at a station: contours, streamlines relative to the body, the
    body's outline, and an inset that follows the body."""

    name = "section"
    KEYS = FlowPanel.COMMON + CutPanel.CUT + ("station", "streamlines", "inset")
    STREAM_KEYS = ("relative", "density", "colour", "opacity", "width", "arrow", "resolution")
    INSET_KEYS = ("offset", "half", "at", "density", "box")

    def parse(self, options, check):
        from flowreel import tracks as tracks_mod
        if "station" not in options:
            raise check.error("missing key 'station' (where along the body to cut)")
        try:
            self.station = tracks_mod.parse(options["station"], kind="number", name="station")
        except ValueError as exc:
            raise check.at("station").wrap(exc) from None
        super().parse(options, check)
        self.streamlines = self._streamlines(options.get("streamlines", {}), check.at("streamlines"))
        self.inset = self._inset(options.get("inset"), check.at("inset"))
        if options.get("view") is None and self.inset is not None:
            self.view = (0.04, 0.08, 0.5, 0.84)

    def _streamlines(self, value, check: Checker):
        if value is False or value is None:
            return None
        spec = check.mapping(value, self.STREAM_KEYS)
        relative = spec.get("relative", True)
        if not isinstance(relative, bool):
            raise check.at("relative").error(f"expected true or false, got {relative!r}")
        out = {"relative": relative,
               "density": check.at("density").number(spec.get("density", 1.6)),
               "colour": colour(spec.get("colour", "#ffffff"), check.at("colour")),
               "opacity": check.at("opacity").number(spec.get("opacity", 0.55)),
               "width": check.at("width").number(spec.get("width", 0.7)),
               "arrow": check.at("arrow").number(spec.get("arrow", 0.8)),
               "resolution": check.at("resolution").integer(spec.get("resolution", 200), minimum=8)}
        for key in ("density", "width"):
            if out[key] <= 0:
                raise check.at(key).error(f"must be positive, got {out[key]:g}")
        if not 0 <= out["opacity"] <= 1:
            raise check.at("opacity").error(f"expected 0 to 1, got {out['opacity']:g}")
        return out

    def _inset(self, value, check: Checker):
        if value is None or value is False:
            return None
        spec = check.mapping(value, self.INSET_KEYS)
        return {"offset": np.asarray(check.at("offset").numbers(spec.get("offset", [0, 0]), 2)),
                "half": self._half(spec.get("half", 0.2 * self.diameter), check.at("half")),
                "at": self._rect(spec.get("at"), check.at("at"), (0.58, 0.2, 0.38, 0.6)),
                "density": check.at("density").number(spec.get("density", 2.4)),
                "box": colour(spec.get("box", "#f2f2f2"), check.at("box"))}

    def build(self, figure):
        self.figure = figure
        self.main = figure.add_axes(self.view)
        self.small = figure.add_axes(self.inset["at"]) if self.inset else None
        self.shown = None

    def state(self, time: float, index: int = 0) -> dict:
        """What frame ``index`` at ``time`` shows: its ``step`` and ``station``, the
        body's centre in the plane, the ``views`` (``(centre, half, density)``, the main
        view first, then the inset), the cut and outlines, the ``crop`` read and the
        body's velocity (zero unless streamlines are relative)."""
        step = self.step_at(time)
        station = float(self.station.at(index))
        centre = self.body_centre(step, station)
        density = self.streamlines["density"] if self.streamlines else 0
        views = [(centre if self.centre is None else self.centre, self.half, density)]
        if self.inset:
            views.append((centre + self.inset["offset"], self.inset["half"],
                          self.inset["density"]))
        cut, curves, crop = self.read(step, station, [(c - h, c + h) for c, h, _ in views])
        moving = np.zeros(3)
        if self.streamlines and self.streamlines["relative"]:
            moving = fc.body_velocity(self.source, step, self.body, self.axis, station, self.slab)
        return {"step": step, "station": station, "centre": centre, "views": views, "cut": cut,
                "curves": curves, "crop": crop, "body_velocity": moving}

    def update(self, time, index=None):
        index = index or 0
        key = (self.step_at(time), float(self.station.at(index)))
        if key == self.shown:
            return
        try:
            state = self.state(time, index)
        except ValueError as exc:
            raise self.failed(time, exc) from None
        axes = [self.main] + ([self.small] if self.small is not None else [])
        tri = state["cut"].triangulation()
        for ax, (centre, half, density) in zip(axes, state["views"]):
            ax.cla()
            bare(ax, self.style)
            self.draw_cut(ax, state["cut"], state["curves"], centre, half)
            if self.streamlines:
                self.draw_streamlines(ax, tri, state, centre, half, density)
        if self.small is not None:
            from matplotlib.patches import Rectangle
            centre, half, _ = state["views"][1]
            self.main.add_patch(Rectangle(tuple(centre - half), 2 * half[0], 2 * half[1],
                                          fill=False, edgecolor=self.inset["box"],
                                          linewidth=1.5, zorder=4))
        self.shown = key

    def flow_grid(self, tri, state, centre, half):
        """The in-plane velocity seen from the body on a regular grid round ``centre``:
        ``(A, B, across, up)``, masked outside the cut and inside the bodies."""
        from matplotlib.tri import LinearTriInterpolator
        n = self.streamlines["resolution"]
        a = np.linspace(centre[0] - half[0], centre[0] + half[0], n)
        b = np.linspace(centre[1] - half[1], centre[1] + half[1], n)
        A, B = np.meshgrid(a, b)
        velocity = state["cut"].velocity - state["body_velocity"]
        comps = []
        for k in self.axes:
            comps.append(LinearTriInterpolator(tri, velocity[:, k])(A, B))
        mask = np.ma.getmaskarray(comps[0]) | np.ma.getmaskarray(comps[1]) | \
            fc.inside(state["curves"], A, B)
        return A, B, *(np.ma.array(np.ma.getdata(c), mask=mask) for c in comps)

    def draw_streamlines(self, ax, tri, state, centre, half, density) -> None:
        """Streamlines of the cut's in-plane velocity on ``ax``, over the view ``centre``
        +- ``half``, at matplotlib's ``density``; nothing where the flow is still."""
        from matplotlib.colors import to_rgba
        A, B, va, vb = self.flow_grid(tri, state, centre, half)
        if np.ma.count(va) < 4 or not np.ma.abs(va).max() + np.ma.abs(vb).max() > 0:
            return
        s = self.streamlines
        ax.streamplot(A[0], B[:, 0], va, vb, color=to_rgba(s["colour"], s["opacity"]),
                      density=density, linewidth=s["width"], arrowsize=s["arrow"], zorder=2)


@register
class CutsPanel(CutPanel):
    """The same cut at several stations of a body, side by side, each labelled."""

    name = "cuts"
    KEYS = FlowPanel.COMMON + CutPanel.CUT + ("stations", "label", "gap")
    LABEL = "station {station:g}"

    def parse(self, options, check):
        super().parse(options, check)
        if options.get("stations") is None:
            raise check.error("missing key 'stations' (where along the body to cut)")
        items = check.at("stations").sequence(options["stations"], minimum=1)
        self.stations = [check.at("stations", i).number(v) for i, v in enumerate(items)]
        label = options.get("label", self.LABEL)
        if label is False or label is None:
            self.label = None
        else:
            self.label = check.at("label").string(label)
            try:
                self.label.format(station=0.0)
            except (KeyError, IndexError, ValueError) as exc:
                raise check.at("label").error(f"the label takes only {{station}}: {exc}") from None
        self.gap = check.at("gap").number(options.get("gap", 0.008))
        if options.get("view") is None:
            self.view = (0.0, 0.09 if self.label else 0.0, 1.0, 0.91 if self.label else 1.0)
        if not 0 <= self.gap * (len(self.stations) - 1) < self.view[2]:
            raise check.at("gap").error(f"a gap of {self.gap:g} leaves no room for "
                                        f"{len(self.stations)} cuts; make it smaller")

    def rects(self) -> list[tuple[float, float, float, float]]:
        """Each station's axes, side by side across the view, ``gap`` apart."""
        left, bottom, width, height = self.view
        n = len(self.stations)
        each = (width - (n - 1) * self.gap) / n
        return [(left + k * (each + self.gap), bottom, each, height) for k in range(n)]

    def build(self, figure):
        self.axes_list = [figure.add_axes(r) for r in self.rects()]
        self.shown = None

    def state(self, time: float) -> dict:
        """What the frame at ``time`` shows: its ``step`` and, per station, its view
        (``(station, centre, cut, curves, crop)``)."""
        step = self.step_at(time)
        views = []
        for station in self.stations:
            centre = self.body_centre(step, station) if self.centre is None else self.centre
            cut, curves, crop = self.read(step, station, [(centre - self.half, centre + self.half)])
            views.append((station, centre, cut, curves, crop))
        return {"step": step, "views": views}

    def update(self, time, index=None):
        step = self.step_at(time)
        if step == self.shown:
            return
        try:
            state = self.state(time)
        except ValueError as exc:
            raise self.failed(time, exc) from None
        for ax, (station, centre, cut, curves, _) in zip(self.axes_list, state["views"]):
            ax.cla()
            bare(ax, self.style)
            self.draw_cut(ax, cut, curves, centre, self.half)
            if self.label:
                ax.text(0.5, -0.02, self.label.format(station=station), transform=ax.transAxes,
                        ha="center", va="top", color=self.style.text)
        self.shown = step


SIDES = ("x", "-x", "y", "-y", "z", "-z")


@register
class StripPanel(FlowPanel):
    """A body seen from one side, coloured by a wall field, with the line where the
    field is zero."""

    name = "strip"
    KEYS = FlowPanel.COMMON + ("side", "component", "span", "zero", "margin", "aspect")
    ZERO_KEYS = ("colour", "width")

    def parse(self, options, check):
        from flowreel.project.measure import diameter, long_axis
        from flowreel.project.names import require_wall
        super().parse(options, check)
        try:
            require_wall(self.source, self.body, "strip")
        except ValueError as exc:
            raise check.at("body").wrap(exc) from None
        decl = self.declared()
        surface = self.source.body(self.source.steps()[0], self.body)
        axis = (decl.axis if decl else None) or long_axis(surface)
        if axis is None:
            raise check.at("body").error(f"body {self.body!r} is not slender, so it has no "
                                         "span to lay across the strip; declare its 'axis'")
        self.axis = fc.AXES.index(axis)
        if options.get("side") is None:
            raise check.error("missing key 'side' (the side the body is seen from: x, -x, y, "
                              "-y, z or -z)")
        side = check.at("side").choice(str(options["side"]), SIDES)
        self.side = fc.AXES.index(side[-1])
        if self.side == self.axis:
            raise check.at("side").error(f"{side} is the body's axis; see the body from across it")
        sign = -1.0 if side.startswith("-") else 1.0
        look = np.zeros(3)
        look[self.side] = sign                         # from the body towards the eye
        along = np.zeros(3)
        along[self.axis] = 1.0
        self.look = look
        self.up = np.cross(along, -look)              # span to the right, not mirrored
        comp = options.get("component")
        self.component = None if comp is None else fc.AXES.index(
            check.at("component").choice(comp, tuple(fc.AXES)))
        self.span = None
        if options.get("span") is not None:
            lo, hi = check.at("span").numbers(options["span"], 2)
            if lo >= hi:
                raise check.at("span").error(f"expected [low, high] with low < high, got "
                                             f"[{lo:g}, {hi:g}]")
            self.span = (lo, hi)
        zero = options.get("zero", {})
        if zero is False or zero is None:
            self.zero = None
        else:
            spec = check.at("zero").mapping(zero, self.ZERO_KEYS)
            self.zero = {"colour": colour(spec.get("colour", "#f2f2f2"), check.at("zero", "colour")),
                         "width": check.at("zero", "width").number(spec.get("width", 2.5))}
        size = (decl.diameter if decl and decl.diameter else None) or diameter(surface, axis)
        self.margin = check.at("margin").number(options.get("margin", 0.5 * size))
        if self.margin <= 0:
            raise check.at("margin").error(f"must be positive, got {self.margin:g}")
        self.aspect = check.at("aspect").choice(options.get("aspect", "auto"), ("auto", "equal"))

    def build(self, figure):
        self.ax = figure.add_axes(self.view)
        self.shown = None

    def surface(self, step: int):
        """The body at ``step``, cut to ``span``, as triangles."""
        surf = self.source.body(step, self.body)
        if self.span is not None:
            pts = np.asarray(surf.points)
            keep = (pts[:, self.axis] >= self.span[0]) & (pts[:, self.axis] <= self.span[1])
            cells = surf.extract_points(keep, adjacent_cells=False, include_cells=True)
            surf = cells.extract_surface()
            if not surf.n_cells:
                raise ValueError(f"the body has no surface between {self.span[0]:g} and "
                                 f"{self.span[1]:g} along its axis")
        return surf.triangulate().clean()

    def values(self, step: int, surf) -> np.ndarray:
        """The field at each point of ``surf``: an array the source gives on the wall, a
        wall field (computed from the flow next to it, per cell, then averaged to the
        points) or a flow field sampled there; one component of a vector."""
        from flowreel import fields
        from flowreel.fields.registry import resolve
        name = self.field
        if name in surf.point_data:
            value = np.asarray(surf.point_data[name], dtype=float)
        else:
            lo = np.asarray(surf.bounds[0::2]) - self.margin
            hi = np.asarray(surf.bounds[1::2]) + self.margin
            flow = self.source.flow(step, fc.source_fields(self.source, [name]), Box(lo, hi))
            if not flow.n_cells:
                raise ValueError("no flow cells round the body; make 'margin' larger than a cell")
            if "wall_frame" in resolve([name]):
                value = fields.compute(flow, [name], wall=surf, **self.params)[name]
                if np.ndim(value) == 0 or len(value) != surf.n_cells:
                    raise ValueError(f"{name!r} is not a field on the wall's cells")
                held = surf.copy()
                held.cell_data["_v"] = np.asarray(value, dtype=float)
                value = np.asarray(held.cell_data_to_point_data().point_data["_v"])
            else:
                if name not in flow.point_data:
                    flow.point_data[name] = fields.compute(flow, [name], **self.params)[name]
                value = np.asarray(surf.sample(flow, pass_point_data=False).point_data[name])
        if value.ndim == 2:
            if self.component is None:
                raise ValueError(f"{name!r} is a vector; say which part with 'component'")
            value = value[:, self.component]
        elif self.component is not None:
            raise ValueError(f"{name!r} is not a vector, so it has no 'component'")
        return value

    def state(self, time: float) -> dict:
        """What the frame at ``time`` shows: its ``step``, the points' ``across`` (along
        the span) and ``up`` coordinates, the visible ``triangles`` and the ``values``."""
        step = self.step_at(time)
        surf = self.surface(step)
        pts = np.asarray(surf.points, dtype=float)
        tris = np.asarray(surf.faces).reshape(-1, 4)[:, 1:]
        middle = pts[tris].mean(axis=1)
        facing = (middle - axis_points(pts, self.axis, middle[:, self.axis])) @ self.look > 0
        return {"step": step, "across": pts[:, self.axis], "up": pts @ self.up,
                "triangles": tris[facing], "values": self.values(step, surf)}

    def update(self, time, index=None):
        from matplotlib.tri import Triangulation
        step = self.step_at(time)
        if step == self.shown:
            return
        try:
            s = self.state(time)
        except (ValueError, TypeError) as exc:
            raise self.failed(time, exc) from None
        ax = self.ax
        ax.cla()
        bare(ax, self.style)
        tri = Triangulation(s["across"], s["up"], s["triangles"])
        self.contours(ax, tri, s["values"])
        used = np.unique(s["triangles"])
        self.zero_line = None
        if self.zero and s["values"][used].min() < 0 < s["values"][used].max():
            self.zero_line = ax.tricontour(tri, s["values"], levels=[0.0], colors=[self.zero["colour"]],
                          linewidths=self.zero["width"])
        a, u = s["across"][used], s["up"][used]
        ax.set_xlim(*(self.span or (a.min(), a.max())))
        pad = 0.04 * (u.max() - u.min())
        ax.set_ylim(u.min() - pad, u.max() + pad)
        ax.set_aspect(self.aspect)
        self.shown = step


def axis_points(points: np.ndarray, axis: int, at: np.ndarray, bins: int = 64) -> np.ndarray:
    """``(len(at), 3)``: the body's centre at the stations ``at``, from its surface
    ``points``: the mean of the points in each of ``bins`` slices along ``axis``,
    interpolated between slices (slices with no point are skipped, so a coarse mesh
    works)."""
    s = points[:, axis]
    edges = np.linspace(s.min(), s.max(), bins + 1)
    which = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, bins - 1)
    count = np.bincount(which, minlength=bins)
    full = count > 0
    sums = np.stack([np.bincount(which, weights=points[:, k], minlength=bins) for k in range(3)], 1)
    centres = sums[full] / count[full, None]
    return np.column_stack([np.interp(at, centres[:, axis], centres[:, k]) for k in range(3)])
