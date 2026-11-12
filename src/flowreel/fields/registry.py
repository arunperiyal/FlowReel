"""Registry of derived fields and the ``compute`` entry point (docs/PLAN.md, Section 6).

A field is a function ``func(grid, *needs, **params)``. ``needs`` are the values of other
registered fields, in the order declared; ``params`` are the function's keyword-only
arguments (those without a default are required). ``compute`` orders the requested fields
by their needs and evaluates every field once, so several fields that need the velocity
gradient share one gradient computation.

The raw inputs ``velocity`` and ``pressure`` are registered here as fields without needs:
they are read from the grid's point data and nothing else is.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from flowreel.sources.base import PRESSURE, VELOCITY, VELOCITY_COMPONENTS


@dataclass(frozen=True)
class Field:
    """A registered field.

    ``name``: the field's name. ``needs``: names of the fields whose values are passed to
    ``func`` after the grid. ``func``: ``func(grid, *needs, **params)``. ``params``: all
    parameter names ``func`` accepts; ``required``: those without a default.
    """

    name: str
    needs: tuple[str, ...]
    func: Callable[..., Any]
    params: tuple[str, ...]
    required: tuple[str, ...]


_FIELDS: dict[str, Field] = {}


def register(name: str, needs=(), *, replace: bool = False):
    """Decorator registering ``func(grid, *needs, **params)`` as the field ``name``.

    ``needs`` lists the fields (or raw inputs ``velocity``, ``pressure``) the function is
    given, in order. Parameters are the function's keyword-only arguments. Registering a
    name twice raises ``ValueError`` unless ``replace`` is true. Returns the function
    unchanged.
    """
    needs = (needs,) if isinstance(needs, str) else tuple(needs)

    def decorator(func):
        if name in _FIELDS and not replace:
            raise ValueError(f"field {name!r} is already registered")
        keyword = [p for p in inspect.signature(func).parameters.values()
                   if p.kind is inspect.Parameter.KEYWORD_ONLY]
        _FIELDS[name] = Field(
            name=name, needs=needs, func=func,
            params=tuple(p.name for p in keyword),
            required=tuple(p.name for p in keyword if p.default is inspect.Parameter.empty))
        return func

    return decorator


def unregister(name: str) -> None:
    """Remove the field ``name`` (used by tests and by plug-ins replacing a field)."""
    _FIELDS.pop(name, None)


def available() -> list[str]:
    """Names of all registered fields, sorted."""
    return sorted(_FIELDS)


def describe(name: str) -> Field:
    """The :class:`Field` record of ``name``; ``KeyError`` lists the known names."""
    try:
        return _FIELDS[name]
    except KeyError:
        raise KeyError(f"unknown field {name!r}; available: {', '.join(available())}") from None


def resolve(names) -> list[str]:
    """Evaluation order for ``names``: every field after the fields it needs, each once.

    Raises ``KeyError`` for an unknown field and ``ValueError`` for circular needs.
    """
    order: list[str] = []
    done: set[str] = set()
    active: list[str] = []

    def visit(name: str) -> None:
        if name in done:
            return
        if name in active:
            raise ValueError("circular needs: " + " -> ".join(active + [name]))
        active.append(name)
        for need in describe(name).needs:
            visit(need)
        active.pop()
        done.add(name)
        order.append(name)

    for name in names:
        visit(name)
    return order


def compute(grid, names, **params) -> dict[str, Any]:
    """Compute the fields ``names`` on ``grid``.

    ``grid``: a pyvista dataset with ``U``, ``V``, ``W`` (or the vector ``velocity``) and,
    for pressure fields, ``p`` as point data. It is not modified.
    ``names``: one name or a list of names.
    ``params``: parameters of the fields (for example ``mu``, ``rho``, ``u_inf``); a
    parameter no requested field accepts, or a missing required one, raises ``TypeError``.

    Returns ``{name: value}`` for the requested names. Point fields are arrays with one
    row per grid point, in the grid's units. Needs are evaluated once per call, however
    many requested fields share them.
    """
    names = [names] if isinstance(names, str) else list(names)
    order = [describe(n) for n in resolve(names)]
    accepted = {p for f in order for p in f.params}
    unknown = sorted(set(params) - accepted)
    if unknown:
        raise TypeError(f"parameter(s) {', '.join(unknown)} not used by the requested fields "
                        f"(accepted: {', '.join(sorted(accepted)) or 'none'})")
    values: dict[str, Any] = {}
    for f in order:
        missing = [p for p in f.required if p not in params]
        if missing:
            raise TypeError(f"field {f.name!r} needs parameter(s): {', '.join(missing)}")
        kwargs = {p: params[p] for p in f.params if p in params}
        values[f.name] = f.func(grid, *(values[n] for n in f.needs), **kwargs)
    return {n: values[n] for n in names}


@register("velocity")
def velocity(grid) -> np.ndarray:
    """Velocity as an ``(n_points, 3)`` array, from ``velocity`` or from ``U``, ``V``, ``W``."""
    data = grid.point_data
    if VELOCITY in data:
        v = np.asarray(data[VELOCITY], dtype=float)
        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError(f"point data {VELOCITY!r} must have three components")
        return v
    missing = [c for c in VELOCITY_COMPONENTS if c not in data]
    if missing:
        raise KeyError(f"grid has no {VELOCITY!r} and lacks {', '.join(missing)} in its point data")
    return np.column_stack([np.asarray(data[c], dtype=float) for c in VELOCITY_COMPONENTS])


@register("pressure")
def pressure(grid) -> np.ndarray:
    """Pressure ``p`` as an ``(n_points,)`` array."""
    if PRESSURE not in grid.point_data:
        raise KeyError(f"grid has no {PRESSURE!r} in its point data")
    return np.asarray(grid.point_data[PRESSURE], dtype=float)
