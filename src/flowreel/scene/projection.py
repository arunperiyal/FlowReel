"""Projection of model points to the screen, for placing captions and arrows."""
from __future__ import annotations

import math

import numpy as np

from flowreel.scene.views import View


def project(view: View, points, size: tuple[int, int]) -> np.ndarray:
    """Pixel positions of model ``points`` seen from ``view`` in a frame of ``size``.

    ``points`` is ``(3,)`` or ``(N, 3)``; ``size`` is ``(width, height)`` in pixels.
    Returns ``(N, 3)``: ``x`` to the right and ``y`` downwards from the frame's top-left
    corner (pixel units, the frame's centre at ``(W/2, H/2)``), and ``depth``, the
    distance in front of the camera along the viewing direction (model units). A
    perspective point at or behind the camera has ``x = y = nan``. ``view_angle`` is the
    vertical angle, ``parallel_scale`` the half frame height, as in VTK.
    """
    w, h = size
    p = np.atleast_2d(np.asarray(points, float)) - np.asarray(view.position, float)
    f = view.direction
    r = np.cross(f, view.up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    x, y, depth = p @ r, p @ u, p @ f
    if view.parallel:
        half = np.full_like(depth, view.parallel_scale)
    else:
        half = depth * math.tan(math.radians(view.view_angle) / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        nx, ny = x / (half * w / h), y / half
    if not view.parallel:
        behind = depth <= 0
        nx[behind] = ny[behind] = np.nan
    return np.column_stack([(nx + 1) / 2 * w, (1 - ny) / 2 * h, depth])
