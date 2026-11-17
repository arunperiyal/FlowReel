"""Layers that need no flow data: ``outline``, ``glyphs``, ``markers3d``, ``geometry``
(plan Section 7.2). Options marked *track* take a number or keys (docs/tracks.md);
positions and lengths are in the source's unit, line widths in pixels.
"""
from __future__ import annotations

import inspect

import numpy as np
import pyvista as pv

from flowreel.box import Box
from flowreel.colours import colormap
from flowreel.scene.errors import Checker
from flowreel.scene.layers import Layer, Option, register
from flowreel.sources.bodies import available_bodies, get_body
from flowreel.tracks import parse as parse_track

AXES = ("x", "y", "z")


def region(spec, data, check: Checker | None = None) -> Box:
    """A box from ``domain``, ``crop`` or ``{x: [lo, hi], y: ..., z: ...}`` (numbers).

    ``domain`` is the source's bounds; ``crop`` the shot's crop (the domain when the shot
    has none).
    """
    if spec == "domain" or (spec == "crop" and data.crop is None):
        return data.source.bounds()
    if spec == "crop":
        return data.crop
    check = check or Checker()
    m = check.mapping(spec, AXES, required=AXES)
    r = [check.at(a).numbers(m[a], 2) for a in AXES]
    return Box(tuple(x[0] for x in r), tuple(x[1] for x in r))


def _check_region(spec, check: Checker) -> None:
    if spec in ("domain", "crop"):
        return
    if isinstance(spec, str):
        raise check.error(f"{spec!r} is not allowed (domain, crop, or {{x: [lo, hi], y: ..., z: ...}})")
    Box_ = check.mapping(spec, AXES, required=AXES)
    for a in AXES:
        lo, hi = check.at(a).numbers(Box_[a], 2)
        if lo >= hi:
            raise check.at(a).error(f"expected [low, high] with low < high, got [{lo:g}, {hi:g}]")


@register
class Outline(Layer):
    """The edges of a box: ``bounds`` (``domain``, ``crop`` or numbers), ``colour``,
    ``width`` (pixels) and ``opacity`` (tracks)."""

    name = "outline"
    options = (
        Option("bounds", track=False, default="domain"),
        Option("colour", "colour", default="#ffffff"),
        Option("width", "number", default=1.0),
        Option("opacity", "number", default=1.0),
    )

    @classmethod
    def check(cls, raw, check):
        _check_region(raw.get("bounds", "domain"), check.at("bounds"))

    def draw(self, plotter, frame) -> None:
        v = frame.values
        box = region(v["bounds"], frame.data)
        edges = pv.Box(bounds=box.to_bounds()).extract_all_edges()
        plotter.add_mesh(edges, color=v["colour"], line_width=v["width"],
                         opacity=v["opacity"], lighting=False)


FACES = tuple(f"{a}{s}" for a in AXES for s in "-+")


def _arrows(points, directions, length: float):
    """Arrow glyphs at ``points`` along ``directions`` (not normalised: zero vectors skipped)."""
    d = np.asarray(directions, float)
    n = np.linalg.norm(d, axis=1)
    keep = n > 1e-12
    cloud = pv.PolyData(np.asarray(points, float)[keep])
    cloud["dir"] = d[keep] / n[keep][:, None]
    if not cloud.n_points:
        return None
    return cloud.glyph(orient="dir", scale=False, factor=length, geom=pv.Arrow())


@register
class Glyphs(Layer):
    """Arrows on a face of a box, or at points.

    Options: ``where`` is ``{face: z-, grid: [n, m], in: domain}`` (arrows at the centres
    of an ``n x m`` grid on that face of the box ``in``: ``x-``, ``x+``, ``y-``, ``y+``,
    ``z-``, ``z+``; the grid runs along the face's two other axes in x, y, z order) or
    ``{points: [[x, y, z], ...]}``. ``direction`` is a vector track, or ``velocity`` to
    point along the local flow (needs the flow; arrows where the flow is zero are
    skipped). ``size`` is the arrow length (track, length unit), ``colour`` and
    ``opacity`` are tracks.
    """

    name = "glyphs"
    allow_text = ("direction",)
    options = (
        Option("where", track=False, required=True),
        Option("direction", "vector", default=(1.0, 0.0, 0.0), doc="vector track, or 'velocity'"),
        Option("size", "number", default=1.0),
        Option("colour", "colour", default="#ffffff"),
        Option("opacity", "number", default=1.0),
    )

    def __init__(self, tracks, raw):
        super().__init__(tracks, raw)
        self.needs_flow = raw.get("direction") == "velocity"

    @classmethod
    def check(cls, raw, check):
        w = check.at("where").mapping(raw["where"], ("face", "grid", "points", "in"))
        if ("points" in w) == ("face" in w):
            raise check.at("where").error("give either 'face' with 'grid', or 'points'")
        if "points" in w:
            for i, p in enumerate(check.at("where", "points").sequence(w["points"], 1)):
                check.at("where", "points", i).numbers(p, 3)
        else:
            check.at("where", "face").choice(w["face"], FACES)
            if "grid" not in w:
                raise check.at("where").error("missing key 'grid'")
            for i, n in enumerate(check.at("where", "grid").sequence(w["grid"])):
                check.at("where", "grid", i).integer(n, minimum=1)
            if len(w["grid"]) != 2:
                raise check.at("where", "grid").error("expected [n, m]")
            _check_region(w.get("in", "domain"), check.at("where", "in"))

    def points(self, data) -> np.ndarray:
        """Where the arrows start."""
        w = self.raw["where"]
        if "points" in w:
            return np.asarray(w["points"], float)
        box = region(w.get("in", "domain"), data)
        k, side = "xyz".index(w["face"][0]), w["face"][1]
        u, v = [a for a in range(3) if a != k]
        n, m = w["grid"]
        a = box.lo[u] + (np.arange(n) + 0.5) / n * (box.hi[u] - box.lo[u])
        b = box.lo[v] + (np.arange(m) + 0.5) / m * (box.hi[v] - box.lo[v])
        gu, gv = np.meshgrid(a, b, indexing="ij")
        pts = np.zeros((n * m, 3))
        pts[:, u], pts[:, v] = gu.ravel(), gv.ravel()
        pts[:, k] = box.lo[k] if side == "-" else box.hi[k]
        return pts

    def directions(self, pts, data, v) -> np.ndarray:
        """Arrow directions at ``pts``."""
        if self.raw.get("direction") != "velocity":
            return np.tile(v["direction"], (len(pts), 1))
        data.need("velocity")
        out = pv.PolyData(pts).sample(data.flow)["velocity"]
        return np.asarray(out)

    def draw(self, plotter, frame) -> None:
        v = frame.values
        pts = self.points(frame.data)
        mesh = _arrows(pts, self.directions(pts, frame.data, v), v["size"])
        if mesh is not None:
            plotter.add_mesh(mesh, color=v["colour"], opacity=v["opacity"], smooth_shading=True)
