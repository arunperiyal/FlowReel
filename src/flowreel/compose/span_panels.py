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
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from flowreel.compose.panels import PanelType, register
from flowreel.compose.series_panel import (LINE_KEYS, find_project, parse_axis, parse_line,
                                           parse_margins)
from flowreel.compose.style import colour
from flowreel.scene.errors import Checker

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
