"""The ``phase`` panel (plan Section 9.2): one history against another.

A pendulum's angle against the cylinder's displacement, say: the trace up to the current
time and a dot at the current values. Both histories are series declared in
``flowreel.yml``, as for the ``series`` panel.

.. code-block:: yaml

    type: phase
    size: [400, 400]
    times: {shot: shots/pendulum.yml}
    x: {body: riser, series: motion, column: y, label: '$y/D$'}
    y: {body: pendulum, series: swing, column: angle, label: '$\\theta$', range: [-0.5, 0.5]}
"""
from __future__ import annotations

import numpy as np

from flowreel.compose.panels import PanelType, register
from flowreel.compose.series_panel import (AXIS_KEYS, LINE_KEYS, find_project, padded,
                                           parse_axis, parse_line, parse_margins, style_axes)
from flowreel.compose.style import colour


@register
class PhasePanel(PanelType):
    """One history against another: the trace to the current time and a dot."""

    name = "phase"
    KEYS = ("x", "y", "colour", "margins")

    def parse(self, options, check):
        project = find_project(self.panel, check)
        self.lines, self.axes = [], []
        for key in ("x", "y"):
            if key not in options:
                raise check.error(f"missing key {key!r}")
            spec = check.at(key).mapping(options[key], LINE_KEYS[:5] + AXIS_KEYS,
                                         required=("series",))
            self.lines.append(parse_line({k: v for k, v in spec.items() if k in LINE_KEYS},
                                         check.at(key), project))
            self.axes.append(parse_axis({k: v for k, v in spec.items() if k in AXIS_KEYS},
                                        check.at(key)))
        self.colour = colour(options.get("colour", self.style.colours[0]), check.at("colour"))
        self.margins = parse_margins(options.get("margins"), check.at("margins"))
        self.check = check

    def files(self):
        return [line.spec.file for line in self.lines]

    def build(self, figure):
        m = self.margins
        ax = figure.add_subplot()
        figure.subplots_adjust(left=m["left"], right=m["right"], top=m["top"], bottom=m["bottom"])
        style_axes(ax, self.style)
        (tx, x), (ty, y) = (line.values(self.check.at(k)) for line, k in zip(self.lines, "xy"))
        self.data = (tx, x, ty, y)
        for axis, values, setter, labeller in ((self.axes[0], x, ax.set_xlim, ax.set_xlabel),
                                               (self.axes[1], y, ax.set_ylim, ax.set_ylabel)):
            setter(*(axis["range"] or padded([values], self.style.pad)))
            if axis["label"]:
                labeller(axis["label"])
        (self.trace,) = ax.plot([], [], color=self.colour, linewidth=self.style.line_width)
        (self.dot,) = ax.plot([], [], "o", color=self.colour, markersize=self.style.dot_size)

    def update(self, time):
        xs, ys = phase_to_time(*self.data, time)
        self.trace.set_data(xs, ys)
        self.dot.set_data(xs[-1:], ys[-1:])


def phase_to_time(tx, x, ty, y, time: float) -> tuple[np.ndarray, np.ndarray]:
    """The trace of ``y`` against ``x`` to ``time``: at every sample time of either
    series before ``time``, then at ``time``, each value interpolated linearly."""
    t = np.union1d(tx, ty)
    t = np.r_[t[t < time], time]
    return np.interp(t, tx, x), np.interp(t, ty, y)

