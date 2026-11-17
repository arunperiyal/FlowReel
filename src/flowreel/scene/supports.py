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
