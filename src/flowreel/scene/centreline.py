"""The ``centreline`` layer: a beam body's axis as a tube (plan Sections 5.6 and 7.2).

In a view of a whole long span the body is a pixel or two thick and its motion, about a
diameter, cannot be seen. The centreline draws the body's axis instead: the centre of
its cross-section at ``count`` stations, as a tube a fraction of a diameter thick,
coloured by its displacement from the **rest line** (the straight line through the
centreline's two ends, which is where a body held at both ends lies at rest).
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
        try:
            colormap(raw.get("colormap", "fire_ice"))
        except ValueError as exc:
            raise check.at("colormap").wrap(exc) from None

    def shape(self, data) -> tuple[str, float, np.ndarray, np.ndarray]:
        """``(axis, diameter, stations, centres)`` of the body at this frame's step."""
        name = self.raw.get("body") or one_body(data.source)
        surface = data.body(name)
        body = declaration(data.source, name)
        axis = (body.axis if body else None) or long_axis(surface)
        if axis is None:
            raise ValueError(f"centreline: body {name!r} is not slender; declare its 'axis' "
                             "in flowreel.yml")
        d = (body.diameter if body else None) or diameter(surface, axis)
        stations, centres = centreline(surface, axis, count=int(self.raw.get("count", 65)),
                                       slab=0.25 * d)
        return axis, d, stations, centres

    def tube(self, stations, centres, d: float, v: dict) -> pv.PolyData:
        """The tube through ``centres``, with the colouring values as ``value``."""
        line = pv.lines_from_points(np.asarray(centres, float))
        colour_by = self.raw.get("colour_by", "none")
        if colour_by != "none":
            line["value"] = displacement_values(colour_by, centres, rest_line(stations, centres))
        return line.tube(radius=v["radius"] * d, n_sides=24, capping=True)

    def draw(self, plotter, frame) -> None:
        v = frame.values
        axis, d, stations, centres = self.shape(frame.data)
        look = dict(opacity=v["opacity"], smooth_shading=v["smooth"],
                    specular=v["specular"], ambient=v["ambient"])
        tube = self.tube(stations, centres, d, v)
        if "value" in tube.point_data:
            plotter.add_mesh(tube, scalars="value", cmap=colormap(self.raw.get("colormap", "fire_ice")),
                             clim=list(self.raw.get("range", (-1.0, 1.0))), show_scalar_bar=False,
                             **look)
        else:
            plotter.add_mesh(tube, color=v["colour"], **look)
