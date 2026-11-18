"""Support symbols: how a body is held, drawn at its ends (plan Section 5.4, "Supports").

A support kind is a registered function that returns the meshes of its symbol for one
:class:`Place`: where the support is and which way is which there. Symbols are built
in the place's own frame and sized in diameters, so they look the same on a body 12 or
500 diameters long:

- ``along``: unit vector along the body's axis, pointing out of the span at this end;
- ``down``: unit vector across the axis, towards the ground the support stands on;
- ``side``: ``along x down``;
- ``size``: the length of one diameter in the picture's model units (the body's
  diameter times the layer's ``size``, enlarged for ``min_pixels``).

A new kind is a function and a call to :func:`register_support`, which also lets
``flowreel.yml`` accept it (with its own keys); no other change to FlowReel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pyvista as pv

from flowreel.project import bodies as bodies_mod
from flowreel.project.bodies import End

Symbol = Callable[[End, "Place"], list]
_symbols: dict[str, Symbol] = {}


@dataclass(frozen=True)
class Place:
    """Where a support is drawn: ``centre`` (the body's centre at the station) and the
    frame ``along``, ``down``, ``side`` (unit vectors), with ``size`` one diameter."""

    centre: np.ndarray
    along: np.ndarray
    down: np.ndarray
    side: np.ndarray
    size: float

    @classmethod
    def make(cls, centre, axis, outward: bool, down, size: float) -> "Place":
        """A place at ``centre`` on a body along ``axis`` (a vector); ``outward`` is
        whether the end looks along ``+axis``. ``down`` is made perpendicular to the
        axis; if it is parallel, another axis is taken."""
        along = np.asarray(axis, float) / np.linalg.norm(axis)
        along = along if outward else -along
        down = np.asarray(down, float)
        down = down - along * float(down @ along)
        if np.linalg.norm(down) < 1e-9:
            other = np.eye(3)[int(np.argmin(np.abs(along)))]
            down = other - along * float(other @ along)
        down = down / np.linalg.norm(down)
        return cls(np.asarray(centre, float), along, down, np.cross(along, down), float(size))

    def point(self, a: float, d: float, s: float) -> np.ndarray:
        """The model point ``a`` along, ``d`` down and ``s`` sideways, in diameters."""
        return self.centre + self.size * (a * self.along + d * self.down + s * self.side)

    def vector(self, a: float, d: float, s: float) -> np.ndarray:
        """The unit direction ``(a, d, s)`` in the place's frame."""
        v = a * self.along + d * self.down + s * self.side
        return v / np.linalg.norm(v)

    def box(self, lo, hi) -> pv.PolyData:
        """A block from ``lo`` to ``hi`` (each ``(along, down, side)`` in diameters)."""
        block = pv.Box(bounds=(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
        matrix = np.eye(4)
        matrix[:3, :3] = self.size * np.column_stack([self.along, self.down, self.side])
        matrix[:3, 3] = self.centre
        return block.transform(matrix, inplace=False)


def register_support(name: str, keys: tuple[str, ...] | None = None,
                     required: tuple[str, ...] = ()):
    """Register ``function(end, place) -> [meshes]`` as the symbol of support ``name``
    (a decorator). ``keys`` are the kind's own keys in ``flowreel.yml`` (``None`` keeps
    those already known), ``required`` those that must be given."""
    def add(fn: Symbol) -> Symbol:
        if keys is not None or name not in bodies_mod.SUPPORTS:
            bodies_mod.SUPPORTS[name] = tuple(keys or ())
            bodies_mod.REQUIRED[name] = tuple(required)
        _symbols[name] = fn
        return fn
    return add


def symbol(end: End, place: Place) -> list:
    """The meshes of ``end``'s support at ``place``."""
    if end.support not in _symbols:
        raise KeyError(f"no symbol for support {end.support!r} (registered: {', '.join(_symbols)})")
    return [m for m in _symbols[end.support](end, place) if m is not None]


def available() -> list[str]:
    """Support kinds with a symbol."""
    return list(_symbols)


@register_support("clamped")
def clamped(end: End, place: Place) -> list:
    """A block the body runs into: 0.8 diameters along the axis, 2 across (the
    prototype's clamps), centred on the station."""
    return [place.box((-0.4, -1.0, -1.0), (0.4, 1.0, 1.0))]


def _cone_and_base(place: Place) -> list:
    """A cone with its tip on the body's underside and a small plate under it."""
    tip, base = place.point(0, 0.5, 0), place.point(0, 1.5, 0)
    cone = pv.Cone(center=(tip + base) / 2, direction=place.vector(0, -1, 0),
                   height=place.size, radius=0.5 * place.size, resolution=32)
    return [cone]


@register_support("pinned")
def pinned(end: End, place: Place) -> list:
    """A cone with its tip on the body, the body free to turn about it, on a plate."""
    return _cone_and_base(place) + [place.box((-0.7, 1.5, -0.7), (0.7, 1.65, 0.7))]


def _axis_vector(value) -> np.ndarray:
    """``x``, ``y``, ``z`` or three numbers, as a unit vector."""
    v = np.eye(3)["xyz".index(value)] if isinstance(value, str) else np.asarray(value, float)
    return v / np.linalg.norm(v)


def _tube(points, radius: float) -> pv.PolyData:
    line = pv.lines_from_points(np.asarray(points, float))
    return line.tube(radius=radius, n_sides=12)


@register_support("roller")
def roller(end: End, place: Place) -> list:
    """The pinned cone on three rollers and a ground plate: held across ``free_along``,
    free to slide along it."""
    free = _axis_vector(end.options["free_along"])
    free = free - place.down * float(free @ place.down)
    free = free / np.linalg.norm(free) if np.linalg.norm(free) > 1e-9 else place.along
    turn = np.cross(place.down, free)
    out = _cone_and_base(place)
    for k in (-1, 0, 1):
        centre = place.point(0, 1.62, 0) + 0.35 * k * place.size * free
        out.append(pv.Cylinder(center=centre, direction=turn, radius=0.12 * place.size,
                               height=1.2 * place.size, resolution=24))
    out.append(place.box((-0.7, 1.74, -0.7), (0.7, 1.86, 0.7)))
    return out


@register_support("spring")
def spring(end: End, place: Place) -> list:
    """A coil from the body's underside to a block on the ground."""
    t = np.linspace(0, 1, 241)
    turns, radius = 5, 0.25
    coil = [place.point(radius * np.cos(2 * np.pi * turns * u), 0.5 + 2 * u,
                        radius * np.sin(2 * np.pi * turns * u)) for u in t]
    return [_tube(coil, 0.035 * place.size), place.box((-0.5, 2.5, -0.5), (0.5, 2.65, 0.5))]


@register_support("free")
def free(end: End, place: Place) -> list:
    """Nothing, or with ``mark: true`` a thin ring round the body at the station."""
    if not end.options.get("mark"):
        return []
    a = np.linspace(0, 2 * np.pi, 97)
    ring = [place.point(0, 0.6 * np.cos(u), 0.6 * np.sin(u)) for u in a]
    return [_tube(ring, 0.04 * place.size)]


@register_support("prescribed")
def prescribed(end: End, place: Place) -> list:
    """A double arrow along ``direction``, through the station: the solver moves it."""
    d = _axis_vector(end.options["direction"])
    out = []
    for sign in (1, -1):
        start = place.centre + sign * 0.6 * place.size * d
        out.append(pv.Arrow(start=start, direction=sign * d, scale=1.2 * place.size,
                            tip_length=0.3, tip_radius=0.12, shaft_radius=0.04))
    return out


def tension_arrow(place: Place) -> pv.PolyData:
    """An arrow 2 diameters long out of the end along the axis: the body is pulled."""
    return pv.Arrow(start=place.point(0.5, 0, 0), direction=place.along, scale=2 * place.size,
                    tip_length=0.25, tip_radius=0.12, shaft_radius=0.04)


# -- the layer ---------------------------------------------------------------------------

from flowreel.scene.layers import Layer, Option, register  # noqa: E402


def pixels_per_unit(camera, point, height: int) -> float:
    """Pixels per model unit at ``point`` in a picture ``height`` pixels high."""
    if camera.parallel_projection:
        return height / (2 * camera.parallel_scale)
    pos, focal = np.asarray(camera.position), np.asarray(camera.focal_point)
    view = (focal - pos) / np.linalg.norm(focal - pos)
    depth = max(float((np.asarray(point) - pos) @ view), 1e-9)
    return height / (2 * depth * np.tan(np.radians(camera.view_angle) / 2))


@register
class Supports(Layer):
    """How the declared bodies are held, drawn at their ends (plan Section 5.4).

    The ends come from ``flowreel.yml`` (``bodies: NAME: ends:``). Each symbol stands at
    the body's centre at its station in this frame, so it moves with the body, and is
    sized in diameters (the declared diameter, else measured), so it looks the same on a
    short or a long body. Options: ``body`` (a name, a list, or ``all``: every declared
    body with ends), ``ends`` (``all`` or a list of indices into the body's ends),
    ``size`` (track, times a diameter), ``min_pixels`` (track, pixels: a diameter of a
    symbol is at least this many pixels, so symbols stay readable in a view of a whole
    long span; 0 is off), ``down`` (vector track: towards the ground the symbols stand
    on), ``colour``, ``opacity``, ``arrow_colour`` (the tension arrows) and the
    material (``ambient``, ``specular``, ``smooth``).
    """

    name = "supports"
    options = (
        Option("body", track=False, default="all", doc="a body name, a list, or all"),
        Option("ends", track=False, default="all", doc="all, or indices into the body's ends"),
        Option("size", "number", default=1.0, doc="symbol scale, in diameters"),
        Option("min_pixels", "number", default=0.0, pixels=True,
               doc="a diameter is at least this many pixels; 0: off"),
        Option("down", "vector", default=(0.0, -1.0, 0.0), doc="towards the ground"),
        Option("colour", "colour", default="#8a9299"),
        Option("opacity", "number", default=1.0),
        Option("arrow_colour", "colour", default="#f5a142", doc="tension arrows"),
        Option("ambient", "number", default=0.4, doc="light the surface gives off, 0..1"),
        Option("specular", "number", default=0.0, doc="weight of the highlight"),
        Option("smooth", "boolean", default=False, doc="smooth shading; false: flat faces"),
    )

    @classmethod
    def check(cls, raw: dict, check) -> None:
        body = raw.get("body", "all")
        if isinstance(body, list):
            for i, name in enumerate(body):
                check.at("body", i).string(name)
        else:
            check.at("body").string(body)
        ends = raw.get("ends", "all")
        if ends != "all":
            for i, k in enumerate(check.at("ends").sequence(ends, 1)):
                check.at("ends", i).integer(k, minimum=0)

    def _bodies(self, source) -> list:
        declared = getattr(source, "declared", None)
        if declared is None:
            raise ValueError("supports: no bodies are declared; declare their ends in "
                             "flowreel.yml (docs/bodies.md)")
        spec = self.raw.get("body", "all")
        if spec == "all":
            return [b for b in declared.values() if b.ends]
        out = []
        for name in ([spec] if isinstance(spec, str) else spec):
            body = source.declaration(name)
            if body is None:
                source.zone(name)                           # KeyError for a wrong name
                raise ValueError(f"supports: body {name!r} is not declared in flowreel.yml")
            if not body.ends:
                raise ValueError(f"supports: body {body.name!r} declares no ends")
            out.append(body)
        return out

    def places(self, plotter, frame) -> list:
        """``(end, place)`` of every support drawn in ``frame``."""
        from flowreel.project.measure import AXES, centre, diameter
        v, data = frame.values, frame.data
        height = plotter.window_size[1]
        out = []
        for body in self._bodies(data.source):
            surface = data.body(body.name)
            d = body.diameter or diameter(surface, body.axis)
            k = AXES[body.axis]
            span = np.asarray(surface.points)[:, k]
            middle = (span.min() + span.max()) / 2
            picks = self.raw.get("ends", "all")
            picks = range(len(body.ends)) if picks == "all" else picks
            for i in picks:
                if i >= len(body.ends):
                    raise ValueError(f"supports: body {body.name!r} has {len(body.ends)} ends, "
                                     f"no end {i}")
                end = body.ends[i]
                try:
                    at = centre(surface, end.at, body.axis, 0.25 * d)
                except ValueError as exc:
                    raise ValueError(f"supports: {body.name} end at {end.at:g}: {exc}") from None
                size = d * v["size"]
                if v["min_pixels"] > 0:
                    px = pixels_per_unit(plotter.camera, at, height)
                    size = max(size, v["min_pixels"] / px)
                out.append((end, Place.make(at, np.eye(3)[k], end.at >= middle, v["down"], size)))
        return out

    def draw(self, plotter, frame) -> None:
        v = frame.values
        look = dict(smooth_shading=v["smooth"], specular=v["specular"], ambient=v["ambient"])
        for end, place in self.places(plotter, frame):
            for mesh in symbol(end, place):
                plotter.add_mesh(mesh, color=v["colour"], opacity=v["opacity"], **look)
            if end.tension:
                plotter.add_mesh(tension_arrow(place), color=v["arrow_colour"],
                                 opacity=v["opacity"], **look)
