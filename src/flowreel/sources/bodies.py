"""Parametric bodies for the ``geometry`` source (docs/PLAN.md, Section 5.3).

A body is a function from keyword parameters to a ``pyvista.PolyData`` surface. It must
be pure: the same parameters give the same surface, so a film can drive any parameter
with a track and cache the result.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pyvista as pv

BodyFunction = Callable[..., pv.PolyData]

_bodies: dict[str, BodyFunction] = {}


def register_body(name: str, function: BodyFunction | None = None):
    """Register ``function`` as the body ``name``.

    Use it as a call, ``register_body("box", make_box)``, or as a decorator,
    ``@register_body("box")``. Raises ``ValueError`` if the name is taken.
    """
    def add(fn: BodyFunction) -> BodyFunction:
        if name in _bodies:
            raise ValueError(f"body {name!r} is already registered")
        _bodies[name] = fn
        return fn

    return add if function is None else add(function)


def available_bodies() -> list[str]:
    """Names of the registered bodies, sorted."""
    return sorted(_bodies)


def get_body(name: str) -> BodyFunction:
    """The function of body ``name``. Raises ``KeyError`` listing the bodies if unknown."""
    try:
        return _bodies[name]
    except KeyError:
        raise KeyError(f"unknown body {name!r}; available: "
                       f"{', '.join(available_bodies()) or 'none'}") from None


def _smoothstep(z, start, end):
    """0 before ``start``, 1 after ``end``, smooth between (a step if they coincide)."""
    if end <= start:
        return (np.asarray(z) >= end).astype(float)
    t = np.clip((z - start) / (end - start), 0, 1)
    return t * t * (3 - 2 * t)


def groove_angle(x, k: int, *, span: float = 12.0, grooves: int = 4, turns: float = 1.0,
                 phase: float = 45.0):
    """Angle in radians of the centre of groove ``k`` at spanwise position ``x``.

    The angle is ``atan2(y, z)`` about the x axis; ``phase`` (degrees) is the angle of
    groove 0 at ``x = 0``. Useful for placing things on a groove (a cutter, an arrow).
    """
    return np.radians(phase) + 2 * np.pi * k / grooves + 2 * np.pi * turns * np.asarray(x) / span


@register_body("grooved_cylinder")
def grooved_cylinder(span: float = 12.0, radius: float = 0.5, grooves: int = 4,
                     depth: float = 0.08, width: float = 0.2, turns: float = 1.0,
                     phase: float = 45.0, cut_front: float | None = None,
                     cut_length: float = 0.25, glow_length: float = 0.8,
                     edge: float = 0.012, samples: tuple[int, int] = (721, 1441),
                     caps: bool = True) -> pv.PolyData:
    """A cylinder along x with helical grooves, whole or partly carved.

    The axis runs from ``x = 0`` to ``x = span``; angles are ``atan2(y, z)``. Lengths
    share one unit (the defaults are in diameters, for the AFMS helical case).

    Arguments:
        span: length of the cylinder.
        radius: radius of the uncut surface.
        grooves: number of grooves, equally spaced around the body (0 for none).
        depth: radial depth at the middle of a groove.
        width: chord width of a groove at the surface.
        turns: turns each groove makes over the span (negative for the other hand,
            0 for straight grooves).
        phase: angle in degrees of the first groove at ``x = 0``.
        cut_front: carving progress: grooves exist for ``x < cut_front``. ``None`` means
            fully carved. Run it from a little below 0 to a little above ``span``.
        cut_length: distance behind the front over which a groove reaches full depth.
        glow_length: distance behind the front over which a new cut is "fresh".
        edge: angle in radians over which a groove wall turns (keeps it smooth).
        samples: points along the span and around the body.
        caps: close the two ends.

    Returns:
        The surface with two point arrays, both from 0 to 1: ``groove`` (how far the
        point is cut, 1 on a groove floor) and ``fresh`` (1 just behind the front,
        fading to 0 over ``glow_length``; all 0 when fully carved), for colour and glow.
    """
    if not 0 <= depth < radius:
        raise ValueError("depth must be at least 0 and below radius")
    if not 0 <= width < 2 * radius:
        raise ValueError("width must be at least 0 and below the diameter")
    n_x, n_theta = (int(n) for n in samples)
    if n_x < 2 or n_theta < 4:
        raise ValueError("samples must be at least (2, 4)")
    x = np.linspace(0.0, span, n_x)[:, None]
    theta = np.linspace(-np.pi, np.pi, n_theta)[None, :]
    half_angle = np.arcsin(width / (2 * radius))
    inside = np.zeros((n_x, n_theta))
    for k in range(int(grooves) if width > 0 else 0):
        centre = groove_angle(x, k, span=span, grooves=grooves, turns=turns, phase=phase)
        off = np.abs((theta - centre + np.pi) % (2 * np.pi) - np.pi)
        inside = np.maximum(inside, 1 - _smoothstep(off, half_angle - edge, half_angle + edge))
    if cut_front is None:
        groove = inside
        fresh = np.zeros_like(inside)
    else:
        behind = cut_front - x
        cut = np.clip(behind / cut_length, 0, 1) if cut_length > 0 else (behind >= 0) * 1.0
        groove = inside * cut
        glow = np.clip(1 - behind / glow_length, 0, 1) if glow_length > 0 else 0.0
        fresh = groove * glow
    r = radius - depth * groove
    grid = pv.StructuredGrid(x * np.ones_like(theta), r * np.sin(theta), r * np.cos(theta))
    # Grid points run along the first axis fastest, so the arrays are flattened that way.
    grid["groove"] = groove.ravel(order="F")
    grid["fresh"] = fresh.ravel(order="F")
    surface = grid.extract_surface(algorithm="dataset_surface")
    for key in ("vtkOriginalPointIds", "vtkOriginalCellIds"):
        for data in (surface.point_data, surface.cell_data):
            if key in data:
                del data[key]
    if not caps:
        return surface
    parts = [surface]
    for end in (0, -1):
        ring = np.c_[np.full(n_theta - 1, x[end, 0]), r[end, :-1] * np.sin(theta[0, :-1]),
                     r[end, :-1] * np.cos(theta[0, :-1])]
        cap = pv.PolyData(ring, np.r_[len(ring), np.arange(len(ring))]).triangulate()
        cap["groove"] = np.zeros(cap.n_points)
        cap["fresh"] = np.zeros(cap.n_points)
        parts.append(cap)
    return pv.merge(parts, merge_points=False)
