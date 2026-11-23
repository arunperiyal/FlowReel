"""Layers that need no flow data: ``outline``, ``glyphs``, ``markers3d``, ``geometry``
(plan Section 7.2). Options marked *track* take a number or keys (docs/guide/shots/tracks.md);
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
        Option("width", "number", default=1.0, pixels=True),
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


def look_options(specular: float) -> tuple[Option, ...]:
    """Options for the look of solid markers and arrows: the material and an arrow's
    proportions (fractions of its length; pyvista's defaults). Shared by glyphs and
    markers3d, each with its own default highlight."""
    return (
        Option("ambient", "number", default=0.0, doc="light the surface gives off, 0..1"),
        Option("specular", "number", default=specular, doc="weight of the highlight"),
        Option("smooth", "boolean", default=True, doc="smooth shading; false: flat faces"),
        Option("tip_length", track=False, default=0.25, doc="arrow head length, fraction"),
        Option("tip_radius", track=False, default=0.1, doc="arrow head radius, fraction"),
        Option("shaft_radius", track=False, default=0.05, doc="arrow shaft radius, fraction"),
    )


def _arrow_shape(v) -> dict:
    return {k: float(v[k]) for k in ("tip_length", "tip_radius", "shaft_radius")}


def _look(v) -> dict:
    return dict(smooth_shading=v["smooth"], specular=v["specular"], ambient=v["ambient"])


def _arrows(points, directions, length: float, shape: dict | None = None):
    """Arrow glyphs at ``points`` along ``directions`` (not normalised: zero vectors
    skipped); ``shape`` holds the arrow's proportions."""
    d = np.asarray(directions, float)
    n = np.linalg.norm(d, axis=1)
    keep = n > 1e-12
    cloud = pv.PolyData(np.asarray(points, float)[keep])
    cloud["dir"] = d[keep] / n[keep][:, None]
    if not cloud.n_points:
        return None
    return cloud.glyph(orient="dir", scale=False, factor=length, geom=pv.Arrow(**(shape or {})))


@register
class Glyphs(Layer):
    """Arrows on a face of a box, or at points.

    Options: ``where`` is ``{face: z-, grid: [n, m], in: domain}`` (arrows at the centres
    of an ``n x m`` grid on that face of the box ``in``: ``x-``, ``x+``, ``y-``, ``y+``,
    ``z-``, ``z+``; the grid runs along the face's two other axes in x, y, z order) or
    ``{points: [[x, y, z], ...]}``. ``direction`` is a vector track, or ``velocity`` to
    point along the local flow (needs the flow; arrows where the flow is zero are
    skipped). ``size`` is the arrow length (track, length unit), ``colour`` and
    ``opacity`` are tracks. ``ambient``, ``specular``, ``smooth`` and the arrow's
    ``tip_length``, ``tip_radius`` and ``shaft_radius`` set its look.
    """

    name = "glyphs"
    allow_text = ("direction",)
    options = (
        Option("where", track=False, required=True,
               doc="{face: x-, grid: [n, m], in: domain} or {points: [[x, y, z], ...]}",
               example={"face": "x-", "grid": [4, 4]}),
        Option("direction", "vector", default=(1.0, 0.0, 0.0), doc="vector track, or 'velocity'"),
        Option("size", "number", default=1.0),
        Option("colour", "colour", default="#ffffff"),
        Option("opacity", "number", default=1.0),
    ) + look_options(specular=0.0)

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
        mesh = _arrows(pts, self.directions(pts, frame.data, v), v["size"], _arrow_shape(v))
        if mesh is not None:
            plotter.add_mesh(mesh, color=v["colour"], opacity=v["opacity"], **_look(v))


@register
class Markers3d(Layer):
    """A solid marker at a model position: an arrow, a block or a sphere.

    Options: ``shape`` (``arrow3d``, ``block`` or ``sphere``, required), ``at`` (vector
    track, the position: an arrow's tail, a block's or a sphere's centre), ``colour``,
    ``opacity``. ``arrow3d`` takes ``direction`` (vector track; its length does not
    matter) and ``length`` (track); ``block`` takes ``size`` (vector track, edge lengths
    along x, y, z); ``sphere`` takes ``radius`` (track). Because every value is a track,
    a marker can move, turn or grow, and a ``series`` track (Phase 2B) can drive it.
    One marker per layer; use several layers for several markers. ``ambient``,
    ``specular``, ``smooth`` and the arrow's proportions set the look, as for glyphs.
    """

    name = "markers3d"
    options = (
        Option("shape", "choice", required=True, choices=("arrow3d", "block", "sphere"),
               example="sphere"),
        Option("at", "vector", required=True, doc="position, length unit",
               example=[0.0, 0.0, 0.0]),
        Option("colour", "colour", default="#ffffff"),
        Option("opacity", "number", default=1.0),
        Option("direction", "vector", default=(1.0, 0.0, 0.0)),
        Option("length", "number", default=1.0),
        Option("size", "vector", default=(1.0, 1.0, 1.0)),
        Option("radius", "number", default=0.5),
    ) + look_options(specular=0.3)

    def mesh(self, v: dict) -> pv.PolyData:
        """The marker's surface at the frame's values."""
        at = np.asarray(v["at"], float)
        shape = v["shape"]
        if shape == "sphere":
            return pv.Sphere(radius=v["radius"], center=at)
        if shape == "block":
            half = np.asarray(v["size"], float) / 2
            return pv.Box(bounds=(at[0] - half[0], at[0] + half[0], at[1] - half[1],
                                  at[1] + half[1], at[2] - half[2], at[2] + half[2]))
        d = np.asarray(v["direction"], float)
        if not np.linalg.norm(d):
            raise ValueError("markers3d arrow3d: direction is the zero vector")
        return pv.Arrow(start=at, direction=d / np.linalg.norm(d), scale=v["length"],
                        **_arrow_shape(v))

    def draw(self, plotter, frame) -> None:
        v = frame.values
        plotter.add_mesh(self.mesh(v), color=v["colour"], opacity=v["opacity"], **_look(v))


@register
class GeometryLayer(Layer):
    """A body built from a registered body function, its parameters tracks.

    Options: ``body`` (name of a registered body, such as ``grooved_cylinder``,
    required), ``params`` (mapping of the body's parameters to values or tracks; a
    parameter not listed keeps the body's default), ``colour`` and ``opacity`` (tracks),
    ``colour_by`` (a point array of the built surface, such as ``fresh`` for the carving
    glow; with ``range`` and ``colormap`` for its values), or ``blend`` (a list of
    ``{array, colour, weight}``: each point's colour is ``colour`` plus, for each entry,
    ``weight * array * (entry colour - colour)``, so a carved groove can take one colour
    and a fresh cut another), ``specular``, ``specular_power`` and ``ambient``
    (tracks), ``sharp_edges`` (false: shade across sharp edges, for steep but smooth
    grooves), and ``markers`` (a list of ``{points, radius, colour, opacity, lighting}``:
    a sphere at each point of the body's field data ``points``, such as the carving
    ``cutters``).
    Parameters are checked against the body's signature when the shot is read, so a
    typo fails at once, not at the first frame. The surface is built every frame from
    the tracks' values; the renderer caches it while they do not change.
    """

    name = "geometry"
    options = (
        Option("body", track=False, required=True, doc="a body of the geometry source",
               example="grooved_cylinder"),
        Option("params", track=False, default=None),
        Option("colour", "colour", default="#c8ccd0"),
        Option("opacity", "number", default=1.0),
        Option("specular", "number", default=0.4),
        Option("colour_by", track=False),
        Option("range", track=False, default=(0.0, 1.0)),
        Option("colormap", track=False, default="fire_ice"),
        Option("blend", track=False, doc="[{array, colour, weight}, ...]: tint by point arrays"),
        Option("specular_power", "number", default=20.0, doc="sharpness of the highlight"),
        Option("ambient", "number", default=0.25),
        Option("sharp_edges", "boolean", default=True, doc="false: smooth across sharp edges"),
        Option("markers", track=False,
               doc="[{points, radius, colour, opacity, lighting}, ...]: spheres at body points"),
    )

    @classmethod
    def check(cls, raw, check):
        check.at("body").choice(raw["body"], available_bodies())
        if raw.get("blend") is not None:
            if raw.get("colour_by"):
                raise check.at("blend").error("give colour_by or blend, not both")
            items = check.at("blend").sequence(raw["blend"], 1)
            raw["blend"] = []
            for i, item in enumerate(items):
                where = check.at("blend", i)
                item = where.mapping(item, ("array", "colour", "weight"),
                                     required=("array", "colour"))
                raw["blend"].append({"array": where.at("array").string(item["array"]),
                                     "colour": _colour(item["colour"], where.at("colour")),
                                     "weight": where.at("weight").number(item.get("weight", 1.0))})
        if raw.get("markers") is not None:
            items = check.at("markers").sequence(raw["markers"], 1)
            raw["markers"] = []
            for i, item in enumerate(items):
                where = check.at("markers", i)
                item = where.mapping(item, ("points", "radius", "colour", "opacity", "lighting"),
                                     required=("points", "radius"))
                lighting = item.get("lighting", True)
                if not isinstance(lighting, bool):
                    raise where.at("lighting").error(f"expected true or false, got {lighting!r}")
                raw["markers"].append({
                    "points": where.at("points").string(item["points"]),
                    "radius": where.at("radius").number(item["radius"]),
                    "colour": _colour(item.get("colour", "#ffffff"), where.at("colour")),
                    "opacity": where.at("opacity").number(item.get("opacity", 1.0)),
                    "lighting": lighting})
        params = check.at("params").mapping(raw.get("params") or {},
                                            list(inspect.signature(get_body(raw["body"])).parameters))
        raw["params"] = {}
        raw["_param_tracks"] = {}
        for key, spec in params.items():
            try:
                raw["_param_tracks"][key] = parse_track(spec, name=key)
            except ValueError as exc:
                raise check.at("params", key).wrap(exc) from None

    def values(self, frame: float) -> dict:
        """Every option's value, with ``params`` evaluated at ``frame``."""
        out = super().values(frame)
        out["params"] = {k: _plain(t.at(frame)) for k, t in self.raw["_param_tracks"].items()}
        out.pop("_param_tracks", None)
        return out

    def mesh(self, v: dict) -> pv.PolyData:
        """The body built with the frame's parameters."""
        return get_body(v["body"])(**v["params"])

    def draw(self, plotter, frame) -> None:
        v = frame.values
        surf = self.mesh(v)
        common = dict(smooth_shading=True, split_sharp_edges=v["sharp_edges"],
                      opacity=v["opacity"], specular=v["specular"],
                      specular_power=v["specular_power"], ambient=v["ambient"])
        if v.get("colour_by"):
            plotter.add_mesh(surf, scalars=v["colour_by"], cmap=colormap(v["colormap"]),
                             clim=list(v["range"]), show_scalar_bar=False, **common)
        elif v.get("blend"):
            surf["rgb"] = self.blend(surf, v)
            plotter.add_mesh(surf, scalars="rgb", rgb=True, show_scalar_bar=False, **common)
        else:
            plotter.add_mesh(surf, color=v["colour"], **common)
        for m in v.get("markers") or ():
            spheres = self.markers(surf, m)
            if spheres is not None:
                plotter.add_mesh(spheres, color=m["colour"], opacity=m["opacity"],
                                 lighting=m["lighting"])

    @staticmethod
    def blend(surf, v) -> np.ndarray:
        """Point colours (uint8 RGB) of ``colour`` tinted by the ``blend`` entries."""
        base = np.asarray(v["colour"], float)
        rgb = np.tile(base, (surf.n_points, 1))
        for b in v["blend"]:
            if b["array"] not in surf.point_data:
                raise ValueError(f"layer geometry: blend array {b['array']!r} is not on the body "
                                 f"(it has: {', '.join(surf.point_data.keys())})")
            amount = b["weight"] * np.asarray(surf[b["array"]], float)[:, None]
            rgb += amount * (np.asarray(b["colour"]) - base)
        return np.rint(np.clip(rgb, 0, 1) * 255).astype(np.uint8)

    @staticmethod
    def markers(surf, m):
        """Spheres at the points of field data ``m['points']``, or ``None`` when the body
        has none at this frame (the cutters exist only while the front is on the span)."""
        if m["points"] not in surf.field_data:
            return None
        pts = np.asarray(surf.field_data[m["points"]], float).reshape(-1, 3)
        if not len(pts):
            return None
        return pv.merge([pv.Sphere(radius=m["radius"], center=p) for p in pts])


def _colour(value, check: Checker) -> tuple:
    from flowreel.tracks import parse_colour
    try:
        return tuple(parse_colour(value))
    except ValueError as exc:
        raise check.wrap(exc) from None


def _plain(value):
    """Tracks give tuples for vectors; bodies may want lists or numbers."""
    return list(value) if isinstance(value, tuple) else value
