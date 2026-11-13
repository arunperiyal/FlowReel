"""Adapter registry. Adapters register under the ``flowreel.sources`` entry-point group
(or with :func:`register` in code), so a new format is a plugin."""
from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable

from flowreel.sources.base import Source

ENTRY_POINT_GROUP = "flowreel.sources"

_registered: dict[str, Callable[..., Source]] = {}


def register(name: str, factory: Callable[..., Source]) -> None:
    """Register ``factory`` (called with the source's options) under ``name``."""
    if name in _registered:
        raise ValueError(f"source adapter {name!r} is already registered")
    _registered[name] = factory


def _entry_points() -> dict[str, Callable[..., Source]]:
    return {ep.name: ep for ep in entry_points(group=ENTRY_POINT_GROUP)}


def available() -> list[str]:
    """Names of all adapters, registered in code or by entry point."""
    return sorted(set(_registered) | set(_entry_points()))


def create(name: str, **options) -> Source:
    """Build the adapter ``name`` with ``options``.

    Raises ``KeyError`` listing the available adapters when ``name`` is unknown.
    """
    if name in _registered:
        return _registered[name](**options)
    eps = _entry_points()
    if name in eps:
        return eps[name].load()(**options)
    raise KeyError(f"unknown source adapter {name!r}; available: {', '.join(available()) or 'none'}")
