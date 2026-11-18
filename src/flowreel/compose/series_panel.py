"""The ``series`` panel (plan Section 9.2): time histories drawn to the current time.

It reads series declared for bodies in the project's ``flowreel.yml`` (the nearest
one at or above the panel file; plan Section 5.4), a column at a time.

**series.** Rows of axes share one time axis. Each row has lines; a line runs from the
start of its series to the current time and ends there at a dot, at the value
interpolated linearly between the two samples around that time, so a panel drawn
between saved steps (Section 9.3) moves smoothly.

.. code-block:: yaml

    type: series
    size: [640, 1080]
    times: {shot: shots/bare_wake.yml}
    x: {label: '$tU/D$', range: [0, 100]}
    rows:
      - label: '$C_L$'
        lines:
          - {body: bare, series: force, column: cl, label: bare}
          - {body: helical, series: force, column: cl, label: helical}
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flowreel.compose.panels import PanelType, register
from flowreel.compose.style import colour
from flowreel.scene.errors import Checker

LINE_KEYS = ("body", "series", "column", "scale", "offset", "label", "colour")
AXIS_KEYS = ("label", "range")
MARGIN_KEYS = ("left", "right", "top", "bottom", "space")
MARGINS = {"left": 0.18, "right": 0.95, "top": 0.86, "bottom": 0.16, "space": 0.18}


@dataclass
class Line:
    """One history: column ``column`` of the series ``series`` declared for ``body``
    (its declaration ``spec``), times ``scale`` plus ``offset``. ``label`` and
    ``colour`` (``None``: from the style) are for drawing."""

    body: str
    series: str
    column: str | None
    spec: object
    scale: float = 1.0
    offset: float = 0.0
    label: str | None = None
    colour: str | None = None

    def values(self, check: Checker) -> tuple[np.ndarray, np.ndarray]:
        """The times and values, read from the file."""
        from flowreel.project.series import read_series
        try:
            frame = read_series(self.spec)
        except (OSError, ValueError) as exc:
            raise check.error(str(exc)) from None
        if frame.attrs.get("by"):
            raise check.error(f"series {self.series!r} of {self.body!r} is at many points; "
                              "draw it with a map panel")
        columns = [c for c in frame.columns if c != "time"]
        column = self.column
        if column is None:
            if len(columns) != 1:
                raise check.error(f"series {self.series!r} has columns {', '.join(columns)}; "
                                  "say which with 'column'")
            column = columns[0]
        elif column not in columns:
            raise check.at("column").error(f"series {self.series!r} has no column {column!r} "
                                           f"(columns: {', '.join(columns)})")
        t = frame["time"].to_numpy(dtype=float)
        return t, frame[column].to_numpy(dtype=float) * self.scale + self.offset


def to_time(t: np.ndarray, v: np.ndarray, time: float) -> tuple[np.ndarray, np.ndarray]:
    """The line of ``(t, v)`` drawn to ``time``: the samples before it, then the point at
    ``time`` with the value interpolated linearly (held at the ends)."""
    shown = t < time
    return np.r_[t[shown], time], np.r_[v[shown], np.interp(time, t, v)]


def find_project(panel, check: Checker):
    """The project of the panel file; an error when there is none."""
    from flowreel.project import find_project as find, load_project
    found = find(panel.file or ".")
    if found is None:
        raise check.error("no flowreel.yml at or above the panel file, so no series are "
                          "declared; declare the bodies' series there")
    return load_project(found)


def parse_line(spec, check: Checker, project, keys=LINE_KEYS) -> Line:
    """A line's mapping: the series it reads and how it is drawn."""
    spec = check.mapping(spec, keys, required=("series",))
    name = check.at("series").string(spec["series"])
    if spec.get("body") is None:
        owners = [b for b in project.bodies.values() if name in b.series]
        if len(owners) != 1:
            which = ", ".join(b.name for b in owners) or "no body"
            raise check.error(f"series {name!r} is declared for {which}; say which with 'body'")
        body = owners[0]
    else:
        body_name = check.at("body").string(spec["body"])
        if body_name not in project.bodies:
            raise check.at("body").error(f"no body {body_name!r} in {project.file} "
                                         f"(bodies: {', '.join(project.bodies) or 'none'})")
        body = project.bodies[body_name]
        if name not in body.series:
            raise check.at("series").error(f"body {body.name!r} has no series {name!r} "
                                           f"(series: {', '.join(body.series) or 'none'})")
    column = None if spec.get("column") is None else check.at("column").string(spec["column"])
    label = None if spec.get("label") is None else check.at("label").string(spec["label"])
    return Line(body.name, name, column, body.series[name],
                check.at("scale").number(spec.get("scale", 1.0)),
                check.at("offset").number(spec.get("offset", 0.0)), label,
                None if spec.get("colour") is None else colour(spec["colour"], check.at("colour")))


def parse_axis(spec, check: Checker) -> dict:
    """``{label, range}``; ``range`` is ``[low, high]`` or left out (from the data)."""
    spec = check.mapping(spec or {}, AXIS_KEYS)
    out = {"label": None if spec.get("label") is None else check.at("label").string(spec["label"]),
           "range": None}
    if spec.get("range") is not None:
        lo, hi = check.at("range").numbers(spec["range"], 2)
        if lo >= hi:
            raise check.at("range").error(f"expected [low, high] with low < high, got [{lo:g}, {hi:g}]")
        out["range"] = (lo, hi)
    return out


def parse_margins(spec, check: Checker) -> dict:
    """The axes' edges as shares of the figure, and the space between rows."""
    spec = check.mapping(spec or {}, MARGIN_KEYS)
    out = dict(MARGINS)
    for key, v in spec.items():
        out[key] = check.at(key).number(v)
    if not (0 <= out["left"] < out["right"] <= 1 and 0 <= out["bottom"] < out["top"] <= 1):
        raise check.error("expected 0 <= left < right <= 1 and 0 <= bottom < top <= 1")
    return out


def padded(values: list[np.ndarray], pad: float) -> tuple[float, float]:
    """The range of ``values`` with ``pad`` of it added above and below."""
    allv = np.concatenate(values)
    lo, hi = float(allv.min()), float(allv.max())
    if hi == lo:
        return lo - 1, hi + 1
    d = pad * (hi - lo)
    return lo - d, hi + d


def style_axes(ax, style) -> None:
    """The look shared by the panels' axes: grid, no ticks, no top or right edge."""
    ax.set_facecolor(style.background)
    ax.grid(color=style.grid, linewidth=style.grid_width)
    ax.tick_params(length=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


@register
class SeriesPanel(PanelType):
    """Rows of time histories on a shared time axis, each line to the current time."""

    name = "series"
    KEYS = ("x", "rows", "y", "lines", "legend", "margins")

    def parse(self, options, check):
        project = find_project(self.panel, check)
        self.x = parse_axis(options.get("x"), check.at("x"))
        if options.get("rows") is not None:
            for key in ("y", "lines"):
                if options.get(key) is not None:
                    raise check.at(key).error("give 'rows', or one row's 'y' and 'lines'")
            items = check.at("rows").sequence(options["rows"], minimum=1)
            rows = [(check.at("rows", i), r) for i, r in enumerate(items)]
        elif options.get("lines") is not None:
            rows = [(check, {"label": (options.get("y") or {}).get("label"),
                             "range": (options.get("y") or {}).get("range"),
                             "lines": options["lines"]})]
            check.at("y").mapping(options.get("y") or {}, AXIS_KEYS)
        else:
            raise check.error("missing key 'rows' (or one row's 'lines')")
        self.rows = []
        for at, row in rows:
            row = at.mapping(row, ("label", "range", "lines"), required=("lines",))
            axis = parse_axis({k: row[k] for k in AXIS_KEYS if row.get(k) is not None}, at)
            items = at.at("lines").sequence(row["lines"], minimum=1)
            lines = []
            for j, spec in enumerate(items):
                line = parse_line(spec, at.at("lines", j), project)
                if line.colour is None:
                    line.colour = self.style.colours[j % len(self.style.colours)]
                lines.append((line, at.at("lines", j)))
            self.rows.append((axis, lines))
        legend = options.get("legend", True)
        if not isinstance(legend, bool):
            raise check.at("legend").error(f"expected true or false, got {legend!r}")
        self.legend = legend
        self.margins = parse_margins(options.get("margins"), check.at("margins"))

    def files(self):
        return [line.spec.file for _, lines in self.rows for line, _ in lines]

    def build(self, figure):
        from flowreel.compose.panel_file import frame_times
        m = self.margins
        axes = figure.subplots(len(self.rows), 1, sharex=True, squeeze=False)[:, 0]
        figure.subplots_adjust(left=m["left"], right=m["right"], top=m["top"],
                               bottom=m["bottom"], hspace=m["space"])
        st = self.style
        self.artists = []
        for ax, (axis, lines) in zip(axes, self.rows):
            style_axes(ax, st)
            if axis["label"]:
                ax.set_ylabel(axis["label"])
            data = [(line, *line.values(at)) for line, at in lines]
            ax.set_ylim(*(axis["range"] or padded([v for _, _, v in data], st.pad)))
            for line, t, v in data:
                (trace,) = ax.plot([], [], color=line.colour, linewidth=st.line_width,
                                   label=line.label)
                (dot,) = ax.plot([], [], "o", color=line.colour, markersize=st.dot_size)
                self.artists.append((trace, dot, t, v))
        if self.x["label"]:
            axes[-1].set_xlabel(self.x["label"])
        if self.x["range"]:
            axes[-1].set_xlim(*self.x["range"])
        else:
            times = frame_times(self.panel)
            axes[-1].set_xlim(times[0], times[-1] if times[-1] > times[0] else times[0] + 1)
        labelled = [line for line, _ in self.rows[0][1] if line.label]
        if self.legend and labelled:
            axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=len(labelled),
                           frameon=False, labelcolor="linecolor", handlelength=1.2,
                           fontsize=st.font_size)

    def update(self, time):
        for trace, dot, t, v in self.artists:
            trace.set_data(*to_time(t, v, time))
            dot.set_data([time], [np.interp(time, t, v)])
