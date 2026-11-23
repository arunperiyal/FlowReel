"""Parametric bodies for the ``geometry`` source (plan/design.md, Section 5.3).

A body is a function from keyword parameters to a ``pyvista.PolyData`` surface. It must
be pure: the same parameters give the same surface, so a film can drive any parameter
with a track and cache the result.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pyvista as pv

from flowreel.sources._util import outer_surface

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


def segment_start(k: int, *, length: float | None = None, gap: float = 0.0,
                  stagger: float = 0.0) -> float:
    """Where along the span a segment of groove ``k`` starts, in ``[0, length + gap)``:
    groove 0's segments start at ``x = 0``, each next groove's ``stagger`` periods later.
    ``0.0`` for grooves that run the whole span."""
    if length is None:
        return 0.0
    period = length + gap
    return float((k * stagger * period) % period)


def on_segment(x, k: int, *, length: float | None = None, gap: float = 0.0,
               stagger: float = 0.0):
    """True where spanwise position ``x`` is on a segment of groove ``k`` (ends
    included). All true for grooves that run the whole span."""
    x = np.asarray(x, float)
    if length is None:
        return np.ones(x.shape, bool)
    u = (x - segment_start(k, length=length, gap=gap, stagger=stagger)) % (length + gap)
    return u <= length


def _along_segment(x, k, length, gap, stagger, edge_length):
    """How far ``x`` is inside a segment of groove ``k``: 1 inside, 0 in a gap, the
    ends turning over ``edge_length`` either side of the segment's end."""
    period = length + gap
    mid = segment_start(k, length=length, gap=gap, stagger=stagger) + length / 2
    off = np.abs((x - mid + period / 2) % period - period / 2)
    return 1 - _smoothstep(off, length / 2 - edge_length, length / 2 + edge_length)


@register_body("grooved_cylinder")
def grooved_cylinder(span: float = 12.0, radius: float = 0.5, grooves: int = 4,
                     depth: float = 0.08, width: float = 0.2, turns: float = 1.0,
                     phase: float = 45.0, length: float | None = None, gap: float = 0.0,
                     stagger: float = 0.0, cut_front: float | None = None,
                     cut_length: float = 0.25, glow_length: float = 0.8,
                     edge: float = 0.012, samples: tuple[int, int] = (721, 1441),
                     caps: bool = True) -> pv.PolyData:
    """A cylinder along x with helical or straight grooves, whole or in segments,
    whole or partly carved.

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
        length: length along the span of one segment of a groove; ``None`` (the
            default) for grooves that run the whole span.
        gap: length along the span between two segments of one groove.
        stagger: shift along the span of each groove's segments from the previous
            groove's, as a fraction of ``length + gap`` (0.5: neighbours half a period
            apart, like bricks). Groove 0's first segment starts at ``x = 0``.
        cut_front: carving progress: grooves exist for ``x < cut_front``. ``None`` means
            fully carved. Run it from a little below 0 to a little above ``span``.
        cut_length: distance behind the front over which a groove reaches full depth.
        glow_length: distance behind the front over which a new cut is "fresh".
        edge: angle in radians over which a groove wall turns (keeps it smooth); the
            ends of a segment turn over the same arc, ``edge * radius`` along the span.
        samples: points along the span and around the body.
        caps: close the two ends.

    Returns:
        The surface with two point arrays, both from 0 to 1: ``groove`` (how far the
        point is cut, 1 on a groove floor) and ``fresh`` (1 just behind the front,
        fading to 0 over ``glow_length``; all 0 when fully carved), for colour and glow.
        Field data ``cutters`` holds one point for each groove whose segment the front
        is on, where the groove meets the front on the uncut surface (``n x 3``), while
        ``0 <= cut_front <= span`` and the front is on some segment; it is absent
        otherwise. A layer can mark them (the geometry layer's ``markers``).
    """
    if not 0 <= depth < radius:
        raise ValueError("depth must be at least 0 and below radius")
    if not 0 <= width < 2 * radius:
        raise ValueError("width must be at least 0 and below the diameter")
    if length is not None:
        if length <= 0:
            raise ValueError("length must be positive (leave it out for whole grooves)")
        if gap < 0:
            raise ValueError("gap must be at least 0")
    elif gap or stagger:
        raise ValueError("gap and stagger need a segment length")
    segments = dict(length=length, gap=gap, stagger=stagger)
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
        across = 1 - _smoothstep(off, half_angle - edge, half_angle + edge)
        if length is not None and gap > 0:
            across = across * _along_segment(x, k, length, gap, stagger, edge * radius)
        inside = np.maximum(inside, across)
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
    surface = outer_surface(grid)
    if not caps:
        return _with_cutters(surface, cut_front, span, radius, grooves, turns, phase,
                             segments)
    parts = [surface]
    for end in (0, -1):
        ring = np.c_[np.full(n_theta - 1, x[end, 0]), r[end, :-1] * np.sin(theta[0, :-1]),
                     r[end, :-1] * np.cos(theta[0, :-1])]
        cap = pv.PolyData(ring, np.r_[len(ring), np.arange(len(ring))]).triangulate()
        cap["groove"] = np.zeros(cap.n_points)
        cap["fresh"] = np.zeros(cap.n_points)
        parts.append(cap)
    return _with_cutters(pv.merge(parts, merge_points=False), cut_front, span, radius,
                         grooves, turns, phase, segments)


def _with_cutters(surface, front, span, radius, grooves, turns, phase, segments):
    """Add field data ``cutters`` (where each groove the front is cutting meets it) while
    the front is on the span and on some groove's segment."""
    if front is not None and 0 <= front <= span and int(grooves) > 0:
        cutting = [k for k in range(int(grooves)) if segments["gap"] == 0
                   or bool(on_segment(front, k, **segments))]
        a = np.array([groove_angle(front, k, span=span, grooves=grooves, turns=turns,
                                   phase=phase) for k in cutting])
        if len(a):
            surface.field_data["cutters"] = np.c_[np.full(len(a), front),
                                                  radius * np.sin(a), radius * np.cos(a)]
    return surface


# -- shapes for virtual bodies (plan Section 5.5) ----------------------------------------
# A virtual body is drawn from its origin, the point it is attached at; lengths are in
# the source's unit; angles in radians.


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("a direction cannot be the zero vector")
    return v / n


def _rotate(v, axis, angle: float) -> np.ndarray:
    """``v`` turned by ``angle`` radians about ``axis`` (right hand)."""
    k = _unit(axis)
    v = np.asarray(v, float)
    return (v * np.cos(angle) + np.cross(k, v) * np.sin(angle)
            + k * float(k @ v) * (1 - np.cos(angle)))


def _rod(start, end, radius: float) -> pv.PolyData:
    start, end = np.asarray(start, float), np.asarray(end, float)
    length = float(np.linalg.norm(end - start))
    if length == 0:
        return pv.Sphere(radius=radius, center=start)
    return pv.Cylinder(center=(start + end) / 2, direction=end - start, radius=radius,
                       height=length, resolution=24).triangulate()


def _merge(parts) -> pv.PolyData:
    merged = pv.merge([p.triangulate() for p in parts], merge_points=False)
    return merged if isinstance(merged, pv.PolyData) else merged.extract_surface()


@register_body("pendulum")
def pendulum(length: float = 1.0, bob: float = 0.2, rod: float = 0.03, angle: float = 0.0,
             down=(0.0, -1.0, 0.0), swing=(0.0, 0.0, 1.0)) -> pv.PolyData:
    """A rod from the pivot (the origin) to a ball.

    ``length`` from pivot to the ball's centre, ``bob`` the ball's radius, ``rod`` the
    rod's radius. ``angle`` (radians) turns it from hanging along ``down`` about the
    ``swing`` axis (right hand), so ``angle: {series: pendulum, column: pendDisp}``
    swings it. What the solver's numbers mean (an angle, the plane) is stated here.
    """
    tip = _rotate(_unit(down) * length, swing, angle)
    return _merge([pv.Sphere(radius=2 * rod, center=(0, 0, 0)), _rod((0, 0, 0), tip, rod),
                   pv.Sphere(radius=bob, center=tip, theta_resolution=32, phi_resolution=32)])


@register_body("spring")
def spring(length: float = 1.0, radius: float = 0.15, turns: float = 8.0, wire: float = 0.02,
           direction=(0.0, -1.0, 0.0)) -> pv.PolyData:
    """A coil from the origin along ``direction``, ``length`` long (drive it to stretch),
    of coil ``radius``, ``turns`` turns and ``wire`` radius."""
    d = _unit(direction)
    a = _unit(np.cross(d, np.eye(3)[int(np.argmin(np.abs(d)))]))
    b = np.cross(d, a)
    u = np.linspace(0, 1, max(int(turns * 32), 16) + 1)
    phase = 2 * np.pi * turns * u
    points = (u[:, None] * length * d + radius * (np.cos(phase)[:, None] * a
                                                   + np.sin(phase)[:, None] * b))
    return pv.lines_from_points(points).tube(radius=wire, n_sides=12).triangulate()


@register_body("mass")
def mass(size: float = 0.3, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> pv.PolyData:
    """A block of edge ``size`` centred at ``(x, y, z)`` from the origin: drive ``x``,
    ``y`` or ``z`` with a displacement series to move it."""
    h = size / 2
    return pv.Box(bounds=(x - h, x + h, y - h, y + h, z - h, z + h)).triangulate()
