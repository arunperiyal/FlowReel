"""Camera framing helpers: ``fit`` a box and ``follow`` a body (plan Section 7.4)."""
from __future__ import annotations

import math

import numpy as np

from flowreel.box import Box
from flowreel.scene.views import View

AXES = {"x": 0, "y": 1, "z": 2}


def fit(view: View, box: Box, margin: float = 1.1, aspect: float | None = None) -> View:
    """Place the camera along ``view``'s direction so that ``box`` is shown whole.

    The focal point moves to the box centre and the viewing direction and ``up`` are
    kept. Without ``aspect``, the box is replaced by its bounding sphere (radius ``r``,
    so the fit holds for any rotation and any picture at least as wide as it is tall, at
    the price of some spare room; VTK's view angle is vertical, so a narrower picture
    cuts the sphere at its sides), enlarged by ``margin`` (> 0, default 1.1). Perspective: distance
    ``r*margin / sin(angle/2)``. Parallel: the position distance is kept and
    ``parallel_scale`` becomes ``r*margin``.

    With ``aspect`` (the picture's width over its height), the box itself is fitted to
    a picture of that shape: its corners, ``margin`` times as far from the centre,
    just in frame. A flat domain seen face on then fills the picture.
    """
    if margin <= 0:
        raise ValueError(f"margin must be positive, got {margin}")
    centre = np.array(box.center)
    radius = 0.5 * float(np.linalg.norm(box.size)) * margin
    if radius == 0:
        raise ValueError("cannot fit an empty box")
    d = view.direction
    if aspect is not None:
        return _fit_picture(view, box, centre, d, margin, aspect)
    if view.parallel:
        return view.with_(position=tuple(centre - d * view.distance), focal=tuple(centre),
                          parallel_scale=radius)
    dist = radius / math.sin(math.radians(view.view_angle) / 2)
    return view.with_(position=tuple(centre - d * dist), focal=tuple(centre))


def _fit_picture(view: View, box: Box, centre, d, margin: float, aspect: float) -> View:
    if aspect <= 0:
        raise ValueError(f"aspect must be positive, got {aspect}")
    right = np.cross(d, np.asarray(view.up, float))
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    half = np.array(box.size) / 2
    corners = centre + half * np.array([[i, j, k] for i in (-1, 1) for j in (-1, 1)
                                        for k in (-1, 1)])
    offset = (corners - centre) * margin
    across = np.maximum(np.abs(offset @ up), np.abs(offset @ right) / aspect)
    if view.parallel:
        return view.with_(position=tuple(centre - d * view.distance), focal=tuple(centre),
                          parallel_scale=float(across.max()))
    # each corner, at depth z beyond the centre, needs (dist + z) tan(angle/2) >= across
    tan = math.tan(math.radians(view.view_angle) / 2)
    dist = float(np.max(across / tan - offset @ d))
    return view.with_(position=tuple(centre - d * dist), focal=tuple(centre))


def body_centre(surface, station: float, axis: str = "z", slab: float | None = None):
    """Centre of a body's cross-section at ``station`` along ``axis``.

    ``surface`` is the body's ``PolyData`` (``Source.body``). The centre is the mean of
    the surface points within ``slab`` of the station (default
    :func:`flowreel.project.measure.default_slab`: 2% of the body's length, at most a
    quarter of its width), with the axis coordinate set to ``station`` exactly. Raises
    ``ValueError`` when no point lies in the slab.
    """
    from flowreel.project.measure import centre
    return centre(surface, station, axis, slab)


def follow(view: View, centre) -> View:
    """Move ``view`` so its focal point is ``centre``, keeping direction and distance."""
    centre = np.asarray(centre, float)
    return view.with_(focal=tuple(centre),
                      position=tuple(centre - view.direction * view.distance))
