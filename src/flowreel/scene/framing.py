"""Camera framing helpers: ``fit`` a box and ``follow`` a body (plan Section 7.4)."""
from __future__ import annotations

import math

import numpy as np

from flowreel.box import Box
from flowreel.scene.views import View

AXES = {"x": 0, "y": 1, "z": 2}


def fit(view: View, box: Box, margin: float = 1.1) -> View:
    """Place the camera along ``view``'s direction so that ``box`` is shown whole.

    The focal point moves to the box centre and the viewing direction and ``up`` are
    kept. The box is replaced by its bounding sphere (radius ``r``, so the fit is safe
    for any frame aspect and any rotation, at the price of some spare room), enlarged by
    ``margin`` (> 0, default 1.1). Perspective: distance ``r*margin / sin(angle/2)``.
    Parallel: the position distance is kept and ``parallel_scale`` becomes ``r*margin``.
    """
    if margin <= 0:
        raise ValueError(f"margin must be positive, got {margin}")
    centre = np.array(box.center)
    radius = 0.5 * float(np.linalg.norm(box.size)) * margin
    if radius == 0:
        raise ValueError("cannot fit an empty box")
    d = view.direction
    if view.parallel:
        return view.with_(position=tuple(centre - d * view.distance), focal=tuple(centre),
                          parallel_scale=radius)
    dist = radius / math.sin(math.radians(view.view_angle) / 2)
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
