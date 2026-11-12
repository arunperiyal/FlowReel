"""Parametric bodies for the ``geometry`` source (docs/PLAN.md, Section 5.3).

A body is a function from keyword parameters to a ``pyvista.PolyData`` surface. It must
be pure: the same parameters give the same surface, so a film can drive any parameter
with a track and cache the result.
"""
from __future__ import annotations

from typing import Callable

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
