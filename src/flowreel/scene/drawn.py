"""Where the model is drawn: a shot's ``stretch`` scales it after the layers draw.

A ``stretch`` (plan Section 5.6, :class:`flowreel.scene.shot.Stretch`) scales every 3D
actor of the frame, so a span 500 long fits it. Most of what a layer draws should be
scaled: the flow, the body, a centreline. Some things should not: a support's symbol, an
arrow of the axes or a tick keep their shape, and a label goes where the stretched model
is drawn, not where it would be unstretched. While :func:`drawing` is in force for a
renderer (the renderer of a frame being drawn), :func:`scale_of` gives its stretch, and
:func:`keep_shape` undoes it for one mesh about its anchor.
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np

_scales: dict[int, np.ndarray] = {}
ONE = np.ones(3)


@contextmanager
def drawing(renderer, scale=None):
    """While in force, the model of ``renderer`` is drawn scaled by ``scale`` (x, y, z;
    ``None``: not scaled)."""
    if scale is None:
        yield
        return
    _scales[id(renderer)] = np.asarray(scale, float)
    try:
        yield
    finally:
        _scales.pop(id(renderer), None)


def scale_of(renderer) -> np.ndarray:
    """The stretch the model of ``renderer`` is drawn with: ``(1, 1, 1)`` unless a shot
    stretches it."""
    return _scales.get(id(renderer), ONE)


def to_drawn(renderer, point) -> np.ndarray:
    """Where model ``point`` is drawn."""
    return np.asarray(point, float) * scale_of(renderer)


def keep_shape(renderer, mesh, anchor):
    """``mesh`` (built at model ``anchor`` in true proportions) changed so that, once the
    stretch scales it, it is drawn at the stretched anchor in its true shape and size.
    Returns ``mesh``, changed in place; unchanged without a stretch."""
    scale = scale_of(renderer)
    if np.all(scale == 1):
        return mesh
    a = np.asarray(anchor, float)
    mesh.points = a + (np.asarray(mesh.points) - a) / scale
    return mesh
