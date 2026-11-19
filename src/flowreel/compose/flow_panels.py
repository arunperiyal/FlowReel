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
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

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
        self.params = {k: check.at("params", k).number(v) for k, v in params.items()}
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
        from matplotlib.colors import to_rgba
        A, B, va, vb = self.flow_grid(tri, state, centre, half)
        if np.ma.count(va) < 4 or not np.ma.abs(va).max() + np.ma.abs(vb).max() > 0:
            return
        s = self.streamlines
        ax.streamplot(A[0], B[:, 0], va, vb, color=to_rgba(s["colour"], s["opacity"]),
                      density=density, linewidth=s["width"], arrowsize=s["arrow"], zorder=2)
