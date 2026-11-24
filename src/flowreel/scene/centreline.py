"""The ``centreline`` layer: a beam body's axis as a tube (plan Sections 5.6 and 7.2).

In a view of a whole long span the body is a pixel or two thick and its motion, about a
diameter, cannot be seen. The centreline draws the body's axis instead: the centre of
its cross-section at ``count`` stations, as a tube a fraction of a diameter thick,
coloured by its displacement from the **rest line** (the straight line through the
centreline's two ends, which is where a body held at both ends lies at rest).

With ``from: probes`` the centreline comes from a history at many points (a series with
stations, such as FlexFlow Analyzer's probe export) and not the flow files, so a shot of
the whole span's motion over thousands of steps reads no flow data: each station sits
on the rest axis (through ``origin`` along the declared axis) moved by the series'
displacement at the frame's time. ``amplify`` draws the displacement that many times
larger (the colours keep the true values); ``rest`` draws the rest line; ``envelope``
draws the extremes of one displacement component over a range of steps.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from flowreel.colours import colormap
from flowreel.project.measure import AXES, centreline, diameter, long_axis
from flowreel.project.names import declaration, one_body
from flowreel.scene.layers import Layer, Option, register

COLOUR_BY = ("none", "displacement", "dx", "dy", "dz")


def rest_line(stations, centres) -> np.ndarray:
    """Points of the straight line through the first and last centre, at ``stations``."""
    s = np.asarray(stations, float)
    c = np.asarray(centres, float)
    u = (s - s[0]) / (s[-1] - s[0]) if s[-1] != s[0] else np.zeros_like(s)
    return c[0] + u[:, None] * (c[-1] - c[0])


def displacement_values(name: str, centres, rest) -> np.ndarray:
    """The value ``name`` (of :data:`COLOUR_BY`) at each centre: the displacement from
    the rest line, its size or one component, in the source's length unit."""
    d = np.asarray(centres, float) - np.asarray(rest, float)
    if name == "displacement":
        return np.linalg.norm(d, axis=1)
    return d[:, "xyz".index(name[1])]


@register
class Centreline(Layer):
    """A beam body's axis as a tube, coloured by its displacement.

    Options: ``body`` (a body name; default the one body), ``count`` (stations along the
    span, default 65), ``radius`` (track, of the tube, in diameters), ``colour``,
    ``opacity``, ``colour_by`` (``none``, ``displacement`` (size), ``dx``, ``dy`` or
    ``dz``: from the rest line, in the source's length unit), ``range`` and ``colormap``
    of that colouring, and the material (``ambient``, ``specular``, ``smooth``).
    The body's axis and diameter come from its declaration, else are measured.

    ``from: probes`` takes the centreline from ``series`` (a body's history at many
    stations; ``columns`` maps ``x``, ``y``, ``z`` to its displacement columns, default
    ``dx``, ``dy``, ``dz``) about the rest axis through ``origin``. ``amplify`` (track)
    scales the drawn displacement; ``rest`` (track) draws the rest line in
    ``rest_colour``; ``envelope: [first step, last step]`` draws the least and greatest
    ``envelope_axis`` displacement over those steps in ``envelope_colour``.
    """

    name = "centreline"
    options = (
        Option("body", track=False, doc="a body name; default the one body"),
        Option("count", track=False, default=65, doc="stations along the span"),
        Option("radius", "number", default=0.3, doc="tube radius, in diameters"),
        Option("colour", "colour", default="#e0e4e8"),
        Option("opacity", "number", default=1.0),
        Option("colour_by", track=False, default="none", choices=COLOUR_BY,
               doc="displacement from the rest line, its size or a component"),
        Option("range", track=False, default=(-1.0, 1.0), doc="[low, high] of the colour map"),
        Option("colormap", track=False, default="fire_ice"),
        Option("from", track=False, default="surface", choices=("surface", "probes"),
               doc="the body's surface, or a series of probe displacements"),
        Option("series", track=False, default="displacement", doc="with probes: the series"),
        Option("columns", track=False, doc="with probes: {x: dx, y: dy, z: dz}"),
        Option("origin", "vector", default=(0.0, 0.0, 0.0),
               doc="with probes: a point of the rest axis"),
        Option("amplify", "number", default=1.0, doc="displacement drawn this many times larger"),
        Option("rest", "boolean", default=False, doc="draw the rest line"),
        Option("rest_colour", "colour", default="#7f8a94"),
        Option("envelope", track=False, doc="[first step, last step]: extremes over them"),
        Option("envelope_axis", track=False, default="y", choices=("x", "y", "z"),
               doc="the displacement component the envelope shows"),
        Option("envelope_colour", "colour", default="#f5a142"),
        Option("ambient", "number", default=0.2, doc="light the surface gives off, 0..1"),
        Option("specular", "number", default=0.3, doc="weight of the highlight"),
        Option("smooth", "boolean", default=True, doc="smooth shading"),
    )

    @classmethod
    def check(cls, raw: dict, check) -> None:
        if raw.get("body") is not None:
            check.at("body").string(raw["body"])
        check.at("count").integer(raw.get("count", 65), minimum=2)
        check.at("colour_by").choice(raw.get("colour_by", "none"), COLOUR_BY)
        check.at("range").numbers(raw.get("range", (-1.0, 1.0)), 2)
        check.at("from").choice(raw.get("from", "surface"), ("surface", "probes"))
        check.at("series").string(raw.get("series", "displacement"))
        if raw.get("columns") is not None:
            cols = check.at("columns").mapping(raw["columns"], ("x", "y", "z"))
            for k, c in cols.items():
                check.at("columns", k).string(c)
        if raw.get("envelope") is not None:
            lo, hi = check.at("envelope").numbers(raw["envelope"], 2)
            if lo > hi:
                raise check.at("envelope").error("expected [first step, last step]")
        check.at("envelope_axis").choice(raw.get("envelope_axis", "y"), ("x", "y", "z"))
        try:
            colormap(raw.get("colormap", "fire_ice"))
        except ValueError as exc:
            raise check.at("colormap").wrap(exc) from None

    def _body(self, data):
        name = self.raw.get("body") or one_body(data.source)
        return name, declaration(data.source, name)

    def shape(self, data, time: float | None = None, values: dict | None = None):
        """``(axis, diameter, stations, centres, rest)`` of the body: from its surface at
        this frame's step, or from the probes at ``time``; ``rest`` holds the rest-line
        point of each station."""
        name, body = self._body(data)
        if self.raw.get("from", "surface") == "probes":
            return self._from_probes(data, name, body, time, values or {})
        surface = data.body(name)
        axis = (body.axis if body else None) or long_axis(surface)
        if axis is None:
            raise ValueError(f"centreline: body {name!r} is not slender; declare its 'axis' "
                             "in the tag's domain.yml")
        d = (body.diameter if body else None) or diameter(surface, axis)
        stations, centres = centreline(surface, axis, count=int(self.raw.get("count", 65)),
                                       slab=0.25 * d)
        return axis, d, stations, centres, rest_line(stations, centres)

    def _probes(self, data, name):
        frame = data.source.series(self.raw.get("series", "displacement"), body=name)
        if "station" not in frame.columns:
            raise ValueError(f"centreline: series {self.raw.get('series', 'displacement')!r} "
                             f"of body {name!r} has no stations (declare 'by' and 'stations')")
        cols = self.raw.get("columns") or {a: f"d{a}" for a in "xyz" if f"d{a}" in frame.columns}
        if not cols:
            raise ValueError("centreline: the probe series has no dx, dy or dz; map its "
                             "columns with columns: {y: ..., z: ...}")
        return frame, cols

    def _from_probes(self, data, name, body, time, values):
        if body is None or body.axis is None:
            raise ValueError(f"centreline: from probes needs body {name!r} declared with "
                             "an 'axis' in the tag's domain.yml")
        frame, cols = self._probes(data, name)
        stations = np.sort(frame["station"].unique())
        unit = np.eye(3)[AXES[body.axis]]
        origin = np.asarray(values.get("origin", (0.0, 0.0, 0.0)), float)
        rest = origin + (stations - float(origin @ unit))[:, None] * unit
        shift = np.zeros((len(stations), 3))
        by_station = {s: g for s, g in frame.groupby("station")}
        for i, s in enumerate(stations):
            g = by_station[s]
            for a, c in cols.items():
                shift[i, "xyz".index(a)] = np.interp(time, g["time"], g[c])
        d = body.diameter or diameter(data.body(name), body.axis)
        return body.axis, d, stations, rest + shift, rest

    def envelope(self, data, name, stations) -> tuple[np.ndarray, np.ndarray] | None:
        """Least and greatest displacement component (``envelope_axis``) at each
        station over the ``envelope`` steps, or ``None`` without one."""
        span = self.raw.get("envelope")
        if span is None:
            return None
        key = (name, tuple(span), tuple(np.round(stations, 9)))
        memo = self.__dict__.setdefault("_envelopes", {})
        if key in memo:
            return memo[key]
        k = "xyz".index(self.raw.get("envelope_axis", "y"))
        source = data.source
        steps = [s for s in source.steps() if span[0] <= s <= span[1]]
        if not steps:
            raise ValueError(f"centreline: no saved step in envelope {list(span)}")
        if self.raw.get("from", "surface") == "probes":
            frame, cols = self._probes(data, name)
            axis_name = "xyz"[k]
            if axis_name not in cols:
                raise ValueError(f"centreline: the probe series has no {axis_name} column for "
                                 "the envelope")
            t0, t1 = source.time(steps[0]), source.time(steps[-1])
            inside = frame[(frame["time"] >= t0) & (frame["time"] <= t1)]
            by = inside.groupby("station")[cols[axis_name]]
            lo, hi = by.min().reindex(stations).to_numpy(), by.max().reindex(stations).to_numpy()
        else:
            _, body = self._body(data)
            axis = body.axis if body and body.axis else long_axis(data.body(name))
            d = (body.diameter if body else None) or diameter(data.body(name), axis)
            shifts = []
            for step in steps:
                surface = source.body(step, name)
                ends, end_centres = centreline(surface, axis, count=2, slab=0.25 * d)
                _, c = centreline(surface, axis, stations=stations, slab=0.25 * d)
                rest = rest_line(np.concatenate([ends[:1], stations, ends[1:]]),
                                 np.vstack([end_centres[:1], c, end_centres[1:]]))[1:-1]
                shifts.append((c - rest)[:, k])
            lo, hi = np.min(shifts, axis=0), np.max(shifts, axis=0)
        memo[key] = (lo, hi)
        return lo, hi

    def tube(self, stations, centres, d: float, v: dict, rest=None) -> pv.PolyData:
        """The tube through ``centres`` (amplified from ``rest``), with the colouring
        values (the true displacement) as ``value``."""
        centres = np.asarray(centres, float)
        rest = rest_line(stations, centres) if rest is None else np.asarray(rest, float)
        drawn = rest + v.get("amplify", 1.0) * (centres - rest)
        line = pv.lines_from_points(drawn)
        colour_by = self.raw.get("colour_by", "none")
        if colour_by != "none":
            line["value"] = displacement_values(colour_by, centres, rest)
        return line.tube(radius=v["radius"] * d, n_sides=24, capping=True)

    def draw(self, plotter, frame) -> None:
        v = frame.values
        axis, d, stations, centres, rest = self.shape(frame.data, frame.time, v)
        look = dict(opacity=v["opacity"], smooth_shading=v["smooth"],
                    specular=v["specular"], ambient=v["ambient"])
        thin = 0.3 * v["radius"] * d
        if v["rest"]:
            plotter.add_mesh(pv.lines_from_points(rest).tube(radius=thin, n_sides=12),
                             color=v["rest_colour"], **look)
        name, _ = self._body(frame.data)
        env = self.envelope(frame.data, name, stations)
        if env is not None:
            k = "xyz".index(self.raw.get("envelope_axis", "y"))
            for side in env:
                pts = rest.copy()
                pts[:, k] += v["amplify"] * np.asarray(side, float)
                plotter.add_mesh(pv.lines_from_points(pts).tube(radius=thin, n_sides=12),
                                 color=v["envelope_colour"], **look)
        tube = self.tube(stations, centres, d, v, rest)
        if "value" in tube.point_data:
            plotter.add_mesh(tube, scalars="value", cmap=colormap(self.raw.get("colormap", "fire_ice")),
                             clim=list(self.raw.get("range", (-1.0, 1.0))), show_scalar_bar=False,
                             **look)
        else:
            plotter.add_mesh(tube, color=v["colour"], **look)
