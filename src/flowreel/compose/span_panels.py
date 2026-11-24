"""Panels of a long body (plan Sections 5.6 and 9.2): ``map`` and ``locator``.

Both read a history at many points along a body: a series declared with ``by`` (the
column numbering the points) and ``stations`` (where each point is along the body), as
in ``flowreel.yml``:

.. code-block:: yaml

    bodies:
      riser:
        series:
          lift: {file: data/lift_{node}.csv, by: node, stations: data/nodes.csv}

**map.** The history against time (across) and station (up), coloured, filling in from
the left up to the current time. Several bodies stack as rows on one time axis, under
one colour bar.

.. code-block:: yaml

    type: map
    size: [1920, 1080]
    times: [0, 0.05, 0.1]
    x: {label: '$tU/D$'}
    y: {label: 'Span $x/D$', ticks: [3, 6, 9]}
    rows:
      - {body: bare, series: lift, column: cl, title: bare}
      - {body: helical, series: lift, column: cl, title: helical}
    colormap: fire_ice
    range: [-1.5, 1.5]
    colorbar: {label: 'Sectional $C_L$'}

**locator.** Where we are along a long body: its span as a bar, its shape now (the
displacement history, amplified), its supports, and the windows that shots show at
this frame (their crops). Frame ``i`` shows each shot's window of its frame ``i``.

.. code-block:: yaml

    type: locator
    size: [1920, 200]
    times: {shot: travel.yml}
    body: riser
    shape: {series: displacement, column: dy, amplify: 50}
    windows: [{shot: travel.yml, label: window}]
    x: {label: 'Span $x/D$'}
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from flowreel.compose.panels import PanelType, register
from flowreel.compose.series_panel import (LINE_KEYS, find_project, parse_axis, parse_line,
                                           parse_margins)
from flowreel.compose.style import colour
from flowreel.scene.errors import Checker

AXES = "xyz"
#: Marker of each support kind on the locator's bar (``free`` only when ``mark``).
SUPPORT_MARKERS = {"pinned": "^", "roller": "o", "clamped": "s", "spring": "X",
                   "prescribed": "D", "free": "|"}

EPS = 1e-9            # a sample at the current time is shown, despite rounding


def series_files(spec) -> list[Path]:
    """The files a series declaration reads: its file, or every file of a ``{by}``
    pattern, and a stations file."""
    path = Path(spec.file)
    if "{" in path.name:
        head = path.name.split("{")[0]
        tail = path.name.split("}")[-1]
        files = sorted(path.parent.glob(head + "*" + tail))
    else:
        files = [path]
    if isinstance(spec.stations, Path):
        files.append(spec.stations)
    return files


def span_table(line, check: Checker) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(times, stations, values)`` of a history at many points: ``values[i, j]`` at
    ``times[i]`` and ``stations[j]`` (both ascending), times ``scale`` plus ``offset``;
    ``NaN`` where a point has no sample at a time. Without declared stations, the point
    numbers stand in for them."""
    from flowreel.project.series import read_series
    try:
        frame = read_series(line.spec)
    except (OSError, ValueError) as exc:
        raise check.error(str(exc)) from None
    by = frame.attrs.get("by")
    if not by:
        raise check.error(f"series {line.series!r} of {line.body!r} is at one point; declare "
                          "it with 'by' (and 'stations'), or draw it with a series panel")
    where = "station" if "station" in frame.columns else by
    values = [c for c in frame.columns if c not in ("time", by, "station")]
    column = line.column
    if column is None:
        if len(values) != 1:
            raise check.error(f"series {line.series!r} has columns {', '.join(values)}; "
                              "say which with 'column'")
        column = values[0]
    elif column not in values:
        raise check.at("column").error(f"series {line.series!r} has no column {column!r} "
                                       f"(columns: {', '.join(values)})")
    table = frame.pivot_table(index="time", columns=where, values=column, aggfunc="last",
                              dropna=False).sort_index().sort_index(axis=1)
    z = table.to_numpy(dtype=float) * line.scale + line.offset
    return table.index.to_numpy(dtype=float), table.columns.to_numpy(dtype=float), z


@register
class MapPanel(PanelType):
    """A history at many points against time and station, filling in to the current
    time; one row per body, under one colour bar."""

    name = "map"
    KEYS = ("rows", "x", "y", "colormap", "range", "colorbar", "margins", "title_size")
    ROW_KEYS = LINE_KEYS[:5] + ("title", "colour")

    def parse(self, options, check):
        from flowreel.colours import colormap
        project = find_project(self.panel, check)
        items = check.at("rows").sequence(options.get("rows"), minimum=1) \
            if "rows" in options else None
        if items is None:
            raise check.error("missing key 'rows' (the bodies and their series)")
        self.rows = []
        for i, spec in enumerate(items):
            at = check.at("rows", i)
            spec = at.mapping(spec, self.ROW_KEYS, required=("series",))
            line = parse_line({k: v for k, v in spec.items() if k in LINE_KEYS[:5]}, at, project)
            title = None if spec.get("title") is None else at.at("title").string(spec["title"])
            tint = colour(spec.get("colour", self.style.colours[i % len(self.style.colours)]),
                          at.at("colour"))
            self.rows.append((line, title, tint, at))
        self.x = parse_axis(options.get("x"), check.at("x"))
        y = dict(options.get("y") or {})
        ticks = y.pop("ticks", None)
        self.y = parse_axis(y, check.at("y"))
        self.ticks = None if ticks is None else [
            check.at("y", "ticks", k).number(v)
            for k, v in enumerate(check.at("y", "ticks").sequence(ticks))]
        name = options.get("colormap", "fire_ice")
        try:
            colormap(check.at("colormap").string(name))
        except ValueError as exc:
            raise check.at("colormap").wrap(exc) from None
        self.colormap = name
        self.range = None
        if options.get("range") is not None:
            lo, hi = check.at("range").numbers(options["range"], 2)
            if lo >= hi:
                raise check.at("range").error(f"expected [low, high] with low < high, got "
                                              f"[{lo:g}, {hi:g}]")
            self.range = (lo, hi)
        self.colorbar = self._colorbar(options.get("colorbar", {}), check.at("colorbar"))
        self.margins = parse_margins(options.get("margins"), check.at("margins"))
        self.title_size = check.at("title_size").number(
            options.get("title_size", self.style.font_size * 1.3))

    @staticmethod
    def _colorbar(value, check: Checker):
        if value is False:
            return None
        spec = check.mapping(value or {}, ("label", "fraction", "pad"))
        return {"label": None if spec.get("label") is None else check.at("label").string(spec["label"]),
                "fraction": check.at("fraction").number(spec.get("fraction", 0.025)),
                "pad": check.at("pad").number(spec.get("pad", 0.02))}

    def files(self):
        return [f for line, *_ in self.rows for f in series_files(line.spec)]

    def build(self, figure):
        from flowreel.colours import colormap
        m = self.margins
        axes = figure.subplots(len(self.rows), 1, sharex=True, squeeze=False)[:, 0]
        figure.subplots_adjust(left=m["left"], right=m["right"], top=m["top"],
                               bottom=m["bottom"], hspace=m["space"])
        tables = [span_table(line, at) for line, _, _, at in self.rows]
        low, high = self.range or symmetric([z for _, _, z in tables])
        self.images = []
        for ax, (line, title, tint, _), (t, s, z) in zip(axes, self.rows, tables):
            ax.set_facecolor(self.style.background)
            image = ax.pcolormesh(t, s, np.full((len(s), len(t)), np.nan),
                                  cmap=colormap(self.colormap), vmin=low, vmax=high,
                                  shading="nearest")
            self.images.append((image, t, z))
            if self.y["label"]:
                ax.set_ylabel(self.y["label"])
            if title:
                ax.set_title(title, loc="left", color=tint, fontsize=self.title_size)
            ax.tick_params(length=0)
            if self.ticks is not None:
                ax.set_yticks(self.ticks)
            if self.y["range"]:
                ax.set_ylim(*self.y["range"])
        if self.x["label"]:
            axes[-1].set_xlabel(self.x["label"])
        t_all = np.concatenate([t for t, _, _ in tables])
        axes[-1].set_xlim(*(self.x["range"] or (t_all.min(), t_all.max())))
        if self.colorbar is not None:
            bar = figure.colorbar(self.images[0][0], ax=list(axes),
                                  fraction=self.colorbar["fraction"], pad=self.colorbar["pad"])
            if self.colorbar["label"]:
                bar.set_label(self.colorbar["label"])
            bar.outline.set_edgecolor(self.style.grid)

    def update(self, time, index=None):
        for image, t, z in self.images:
            image.set_array(filled(t, z, time).ravel())


def filled(t: np.ndarray, z: np.ndarray, time: float) -> np.ndarray:
    """The map at ``time``, station by time (``z`` transposed): samples up to ``time``
    shown, later ones ``NaN`` (drawn as nothing)."""
    return np.where(t[None, :] <= time + EPS, z.T, np.nan)


def symmetric(tables: list[np.ndarray]) -> tuple[float, float]:
    """``(-a, a)`` with ``a`` the largest magnitude in ``tables``, so a diverging
    colour map has its middle at zero."""
    a = max(float(np.nanmax(np.abs(z))) for z in tables)
    return (-a, a) if a > 0 else (-1.0, 1.0)


@register
class LocatorPanel(PanelType):
    """A long body's span as a bar: its shape now, amplified, its supports and the
    windows on show."""

    name = "locator"
    KEYS = ("body", "shape", "supports", "windows", "x", "y", "colour", "margins")
    SHAPE_KEYS = ("series", "column", "scale", "offset", "amplify", "colour")
    WINDOW_KEYS = ("shot", "colour", "label")

    def parse(self, options, check):
        from flowreel.colours import BODY
        project = find_project(self.panel, check)
        if "body" not in options:
            raise check.error("missing key 'body' (the long body to show)")
        name = check.at("body").string(options["body"])
        try:
            self.body = project.body(name)
        except LookupError as exc:
            raise check.at("body").error(str(exc.args[0])) from None
        if self.body.axis is None:
            raise check.at("body").error(f"body {name!r} has no axis, so no span; declare "
                                         "its 'axis' (in its tag's domain.yml)")
        self.axis = AXES.index(self.body.axis)
        self.colour = colour(options.get("colour", BODY), check.at("colour"))
        self.shape = None
        if options.get("shape") is not None:
            at = check.at("shape")
            spec = at.mapping(options["shape"], self.SHAPE_KEYS, required=("series",))
            line = parse_line({"body": name, **{k: v for k, v in spec.items()
                                                if k in LINE_KEYS[1:5]}}, at, project)
            amplify = at.at("amplify").number(spec.get("amplify", 1.0))
            if amplify <= 0:
                raise at.at("amplify").error(f"must be positive, got {amplify:g}")
            tint = colour(spec.get("colour", self.colour), at.at("colour"))
            self.shape = (line, amplify, tint, at)
        supports = options.get("supports", True)
        if not isinstance(supports, bool):
            raise check.at("supports").error(f"expected true or false, got {supports!r}")
        self.supports = supports
        items = check.at("windows").sequence(options.get("windows") or [])
        self.windows = [self._window(w, check.at("windows", i)) for i, w in enumerate(items)]
        self.x = parse_axis(options.get("x"), check.at("x"))
        self.y = parse_axis(options.get("y"), check.at("y"))
        self.margins = parse_margins({"bottom": 0.3, "top": 0.85, "left": 0.04, "right": 0.98,
                                      **(options.get("margins") or {})}, check.at("margins"))
        if not self.body.ends and self.shape is None and self.x["range"] is None:
            raise check.error(f"body {name!r} declares no ends: give a 'shape' or an x 'range' "
                              "so the span is known")

    def _window(self, spec, check: Checker) -> dict:
        """A shot's window: its crop along the body's axis, per frame."""
        from flowreel.compose.stations import read_shot
        from flowreel.scene.shot import CropAround
        spec = check.mapping(spec, self.WINDOW_KEYS, required=("shot",))
        path = (self.panel.folder / check.at("shot").string(spec["shot"])).resolve()
        shot = read_shot(path, check.at("shot"))
        crop = shot.crop
        if crop is None:
            raise check.at("shot").error(f"shot {shot.name!r} has no crop, so no window to show")
        if isinstance(crop, CropAround):
            if crop.body is not None and crop.body != self.body.name:
                raise check.at("shot").error(f"shot {shot.name!r} crops around {crop.body!r}, "
                                             f"not {self.body.name!r}")
            window = {"station": crop.station, "half": crop.half[self.axis]}
        else:
            window = {"range": (crop.lo[self.axis], crop.hi[self.axis])}
        window["file"] = path
        window["colour"] = colour(spec.get("colour", self.style.colours[0]), check.at("colour"))
        window["label"] = None if spec.get("label") is None else check.at("label").string(spec["label"])
        return window

    def files(self):
        out = [] if self.shape is None else series_files(self.shape[0].spec)
        return out + [w["file"] for w in self.windows]

    def span(self) -> tuple[float, float]:
        """The body's first and last station: its ends, else its shape's points."""
        if self.body.ends:
            stations = [e.at for e in self.body.ends]
        else:
            stations = list(self.table[1]) if self.table is not None else [0.0, 1.0]
        return min(stations), max(stations)

    def build(self, figure):
        from matplotlib.patches import Rectangle

        from flowreel.colours import MUTED
        m = self.margins
        ax = figure.add_subplot()
        figure.subplots_adjust(left=m["left"], right=m["right"], top=m["top"], bottom=m["bottom"])
        ax.set_facecolor(self.style.background)
        for side in ("left", "right", "top"):
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
        ax.set_yticks([])
        self.table = None if self.shape is None else span_table(self.shape[0], self.shape[3])
        lo, hi = self.span()
        reach = 1.0
        if self.table is not None:
            reach = max(float(np.nanmax(np.abs(self.table[2]))) * self.shape[1], 1e-9)
        ylo, yhi = self.y["range"] or (-1.4 * reach, 1.4 * reach)
        ax.set_ylim(ylo, yhi)
        length = hi - lo
        ax.set_xlim(*(self.x["range"] or (lo - 0.03 * length, hi + 0.03 * length)))
        if self.x["label"]:
            ax.set_xlabel(self.x["label"])
        thick = 0.16 * (yhi - ylo)
        ax.add_patch(Rectangle((lo, -thick / 2), length, thick, color=MUTED, alpha=0.45,
                               linewidth=0, zorder=1))
        self.boxes = []
        for w in self.windows:
            box = Rectangle((lo, ylo), 0, yhi - ylo, facecolor=w["colour"], alpha=0.3,
                            edgecolor=w["colour"], linewidth=self.style.grid_width, zorder=2)
            ax.add_patch(box)
            text = None
            if w["label"]:
                text = ax.text(lo, yhi, w["label"], color=w["colour"], ha="center", va="bottom",
                               clip_on=False)
            self.boxes.append((box, text, w))
        self.line = None
        if self.table is not None:
            (self.line,) = ax.plot([], [], color=self.shape[2], linewidth=self.style.line_width,
                                   zorder=3)
        if self.supports:
            self._supports(ax, lo, hi, yhi - ylo)

    def _supports(self, ax, lo: float, hi: float, height: float) -> None:
        size = self.style.dot_size * 1.6
        for end in self.body.ends:
            if end.support == "free" and not end.options.get("mark"):
                continue
            ax.plot([end.at], [0], SUPPORT_MARKERS[end.support], color=self.style.text,
                    markersize=size, zorder=4, clip_on=False)
            if end.tension:
                out = 1 if end.at >= (lo + hi) / 2 else -1
                reach = 0.025 * (hi - lo)
                ax.annotate("", xy=(end.at + out * 2 * reach, 0), xytext=(end.at + out * 0.6 * reach, 0),
                            arrowprops={"arrowstyle": "-|>", "color": self.style.text,
                                        "linewidth": self.style.line_width}, zorder=4,
                            annotation_clip=False)

    def update(self, time, index=None):
        if self.line is not None:
            self.line.set_data(*shape_at(*self.table, time, self.shape[1]))
        for box, text, w in self.boxes:
            a, b = window_at(w, index or 0)
            box.set_x(a)
            box.set_width(b - a)
            if text is not None:
                text.set_x((a + b) / 2)


def shape_at(t, s, z, time: float, amplify: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """The body's shape at ``time``: each station's value interpolated in time
    (held at the ends), times ``amplify``."""
    now = np.array([np.interp(time, t, z[:, j]) for j in range(len(s))])
    return s, now * amplify


def window_at(window: dict, index: int) -> tuple[float, float]:
    """The span a window covers in frame ``index`` of its shot."""
    if "range" in window:
        return window["range"]
    station = window["station"].at(index)
    return station - window["half"], station + window["half"]
