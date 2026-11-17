"""A body's shape measured from its surface: centre at a station, centreline, diameter,
long axis (plan Section 5.4, "Stations").

Everything works on the surface at one step, so it follows a bent and moving body. A
**section** is the surface's points within a slab (half-width ``slab``) of a station
along the axis. The default slab is 2% of the body's length, but no more than a quarter
of its cross-section's width, so a body 500 diameters long is cut into thin slices, not
slabs 10 diameters wide. Lengths are in the source's unit.
"""
from __future__ import annotations

import numpy as np

AXES = {"x": 0, "y": 1, "z": 2}


def _points(surface) -> np.ndarray:
    return np.asarray(surface.points, dtype=float)


def default_slab(surface, axis: str) -> float:
    """Half-width of a section: 2% of the length along ``axis``, at most a quarter of the
    mean width across it."""
    pts, k = _points(surface), AXES[axis]
    ext = np.ptp(pts, axis=0)
    across = float(np.mean(np.delete(ext, k)))
    return max(min(0.02 * float(ext[k]), 0.25 * across), 1e-9)


def section(surface, station: float, axis: str, slab: float | None = None) -> np.ndarray:
    """The surface points within ``slab`` of ``station`` along ``axis``, shape (n, 3),
    each point once (a seam's duplicated points would pull the mean towards it).
    Raises ``ValueError`` when there are none."""
    pts, k = _points(surface), AXES[axis]
    slab = default_slab(surface, axis) if slab is None else slab
    near = pts[np.abs(pts[:, k] - station) <= slab]
    if len(near) == 0:
        raise ValueError(f"the body has no points within {slab:g} of {axis}={station:g}")
    return np.unique(near, axis=0)


def centre(surface, station: float, axis: str = "z", slab: float | None = None) -> tuple:
    """Centre of the section at ``station``: the mean of its points, with the axis
    coordinate set to ``station`` exactly."""
    c = section(surface, station, axis, slab).mean(axis=0)
    c[AXES[axis]] = station
    return tuple(float(v) for v in c)


def _stations(surface, axis: str, count: int, slab: float) -> np.ndarray:
    k = AXES[axis]
    lo, hi = float(_points(surface)[:, k].min()), float(_points(surface)[:, k].max())
    if hi - lo <= 2 * slab:
        return np.array([(lo + hi) / 2])
    return np.linspace(lo + slab, hi - slab, count)


def centreline(surface, axis: str, stations=None, count: int = 33,
               slab: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The body's centreline: ``(stations, centres)``, centres of shape (n, 3).

    ``stations`` default to ``count`` evenly spaced along the body, a slab in from each
    end (the end caps would pull the centre towards the axis' cap).
    """
    slab = default_slab(surface, axis) if slab is None else slab
    at = np.asarray(stations if stations is not None else _stations(surface, axis, count, slab),
                    dtype=float)
    return at, np.array([centre(surface, s, axis, slab) for s in at])


def diameter(surface, axis: str | None = None, count: int = 9, slab: float | None = None) -> float:
    """The body's diameter.

    With ``axis``: the median over ``count`` sections of twice the median distance of a
    section's points from its own axis (a line fitted through the section, so a bent
    body's tilt does not widen it). Medians, so grooves and strakes, which cover less
    than half the circumference, and the ends count for little: it is the bare body's.
    Without: the smallest extent of the bounding box.
    """
    pts = _points(surface)
    if axis is None:
        return float(np.ptp(pts, axis=0).min())
    slab = default_slab(surface, axis) if slab is None else slab
    return float(np.median([2 * _radius(section(surface, s, axis, slab), AXES[axis])
                            for s in _stations(surface, axis, count, slab)]))


def _radius(cut: np.ndarray, k: int) -> float:
    """Median distance of the points of a section from a line fitted through it."""
    along = cut[:, k]
    resid = []
    for j in (i for i in range(3) if i != k):
        if np.ptp(along) > 0:
            fit = np.polyval(np.polyfit(along, cut[:, j], 1), along)
        else:
            fit = cut[:, j].mean()
        resid.append(cut[:, j] - fit)
    return float(np.median(np.hypot(*resid)))


def long_axis(surface, ratio: float = 3.0) -> str | None:
    """The axis along which the body is at least ``ratio`` times longer than across it
    (its span), or ``None`` for a body that is not slender."""
    ext = np.ptp(_points(surface), axis=0)
    k = int(np.argmax(ext))
    across = float(np.max(np.delete(ext, k)))
    return "xyz"[k] if across > 0 and ext[k] >= ratio * across else None
