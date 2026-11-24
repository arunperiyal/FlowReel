"""Camera orbits: an arc of views round a target (plan Section 8.2, ``camera orbit``).

:func:`orbit` places keys on an arc round ``target`` and returns them as named views
and a camera track, ready for :func:`~flowreel.scene.camera_file.update_cameras`::

    views, track = orbit((6, 0, 9.5), radius=12, frames=240, azimuth=-30, span=120,
                         elevation=(10, 35), axis="y", name="turn")

Angles are degrees. The orbit turns about ``axis`` (``x``, ``y``, ``z`` or a vector)
through the target. Azimuth 0 is the reference direction across the axis (``+x`` for
the ``y`` and ``z`` axes, ``+z`` for the ``x`` axis), and a positive ``span`` turns
anticlockwise seen from the tip of the axis. Elevation is the angle above the plane
across the axis, blended from its first to its last value along the arc. ``lead`` moves
the focal point that far along the axis from the target (model units), so a camera
circling a station of a long body looks a little along it.

The keys lie evenly, at most :data:`STEP` degrees apart, on a spline path. A spline
repeats its end keys, so its first and last segments sag inside the circle, by about
0.05% of the radius at 5 degrees (0.4% at 15); between the others the camera keeps to
the circle within 0.0002%. ``ease`` shapes the motion over the whole orbit, not per segment: the
key frames are spaced so the camera starts and stops gently under ``smooth`` (the
segments between them are linear).
"""
from __future__ import annotations

import math

import numpy as np

from flowreel.scene.camera_path import CameraTrack, build_track
from flowreel.scene.views import View
from flowreel.tracks import EASE_NAMES, EASINGS

STEP = 5.0            # degrees between keys, at most
AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def orbit(target, radius: float, frames: int, azimuth: float = 0.0, span: float = 360.0,
          elevation=0.0, axis="y", up=None, lead: float = 0.0, view_angle: float = 30.0,
          ease: str = "smooth", name: str = "orbit") -> tuple[dict[str, View], CameraTrack]:
    """Views and a camera track circling ``target`` (a point, model units).

    ``radius`` is the camera's distance from the target, ``frames`` the track's length
    (the last key at frame ``frames - 1``). ``elevation`` is one angle or ``(from, to)``,
    each within 89 degrees of the plane across the axis. ``up`` defaults to the axis
    (give it for an orbit round a horizontal body). Views are named
    ``<name>_00``, ``<name>_01``, ...; the track is ``frames`` long. Raises
    ``ValueError`` for a bad argument.
    """
    target = np.asarray(target, float)
    if target.shape != (3,):
        raise ValueError(f"target must be [x, y, z], got {target.tolist()}")
    if not radius > 0:
        raise ValueError(f"radius must be positive, got {radius:g}")
    if int(frames) != frames or frames < 2:
        raise ValueError(f"frames must be a whole number of at least 2, got {frames}")
    if span == 0:
        raise ValueError("span must not be 0")
    if ease not in EASE_NAMES or ease == "hold":
        raise ValueError(f"unknown ease {ease!r} for an orbit "
                         f"(allowed: {', '.join(e for e in EASE_NAMES if e != 'hold')})")
    if not 0 < view_angle < 180:
        raise ValueError(f"view_angle must be between 0 and 180 degrees, got {view_angle:g}")
    el = (float(elevation), float(elevation)) if np.isscalar(elevation) else tuple(map(float, elevation))
    if len(el) != 2 or max(abs(e) for e in el) > 89:
        raise ValueError(f"elevation must be one angle or [from, to], each within 89 "
                         f"degrees, got {elevation}")
    if isinstance(axis, str) and axis not in AXES:
        raise ValueError(f"axis must be x, y, z or [x, y, z], got {axis!r}")
    k = _unit(AXES[axis] if isinstance(axis, str) else axis, "axis")
    e1 = _unit(_across(k), "axis")
    e2 = np.cross(k, e1)
    up = k if up is None else _unit(up, "up")
    focal = target + lead * k
    views, keys = {}, []
    for i, s in enumerate(_fractions(abs(span))):
        az = math.radians(azimuth + span * s)
        elev = math.radians(el[0] + (el[1] - el[0]) * s)
        out = math.cos(elev) * (math.cos(az) * e1 + math.sin(az) * e2) + math.sin(elev) * k
        position = target + radius * out
        direction = focal - position
        if np.linalg.norm(np.cross(direction, up)) < 1e-6 * np.linalg.norm(direction):
            raise ValueError(f"key {i}: 'up' is parallel to the viewing direction; "
                             f"give another 'up'")
        key = f"{name}_{i:02d}"
        views[key] = View(_tuple(position), _tuple(focal), _tuple(up), float(view_angle),
                          name=key)
        keys.append((_frame(s, ease, frames - 1), key))
    return views, build_track(views, keys, path="spline", ease="linear", frames=int(frames))


def body_target(source, body: str | None, station: float, step: int | None = None,
                axis: str | None = None):
    """The centre of ``body`` at ``station`` along its axis, at ``step`` (default the
    source's first), and that axis: the target of an orbit round a body.

    ``body`` is a name declared in a tag's ``domain.yml`` or a zone of the source, ``None`` for
    the one body there is. The axis is ``axis``, else the declared one, else the body's
    measured long axis, else ``z``, as ``follow`` takes it (docs/guide/shots/cameras.md).
    """
    from flowreel.project.measure import long_axis
    from flowreel.project.names import declaration, one_body
    from flowreel.scene.framing import body_centre
    name = body if body is not None else one_body(source)
    step = source.steps()[0] if step is None else step
    surface = source.body(step, name)
    decl = declaration(source, name)
    axis = axis or (decl.axis if decl else None) or long_axis(surface) or "z"
    slab = 0.25 * decl.diameter if decl and decl.diameter else None
    return tuple(float(x) for x in body_centre(surface, station, axis, slab)), axis


def _fractions(span: float) -> list[float]:
    """Where the keys lie, as fractions of the turn: evenly, at most :data:`STEP`
    degrees apart (a uniform spline overshoots between keys spaced unevenly)."""
    n = max(1, math.ceil(span / STEP))
    return [i / n for i in range(n + 1)]


def _frame(s: float, ease: str, last: int) -> float:
    """The frame at which an orbit eased by ``ease`` has gone the fraction ``s``."""
    if s <= 0 or s >= 1:
        return float(last) * (s >= 1)
    f, lo, hi = EASINGS[ease], 0.0, 1.0
    for _ in range(60):                         # every easing here rises: bisect
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < s else (lo, mid)
    return round((lo + hi) / 2 * last, 6)


def _across(k: np.ndarray) -> np.ndarray:
    """The reference direction across the axis ``k``: ``+x``, or ``+z`` when ``k`` is
    close to ``x``; made square to ``k``."""
    ref = np.array([0.0, 0.0, 1.0]) if abs(k[0]) > 0.9 else np.array([1.0, 0.0, 0.0])
    return ref - (ref @ k) * k


def _unit(v, what: str) -> np.ndarray:
    v = np.asarray(v, float)
    if v.shape != (3,) or not np.linalg.norm(v) > 0:
        raise ValueError(f"{what} must be x, y, z or a non-zero [x, y, z], got {v.tolist()}")
    return v / np.linalg.norm(v)


def _tuple(v) -> tuple[float, float, float]:
    return tuple(round(float(x), 9) + 0.0 for x in v)
