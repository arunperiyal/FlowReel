"""Colour maps and colours shared by the layers."""
from __future__ import annotations

from matplotlib.colors import LinearSegmentedColormap

#: Diverging map that is black at zero, so weak flow fades into a black background:
#: ice blue for negative values, fire for positive (the prototype's).
FIRE_ICE = LinearSegmentedColormap.from_list(
    "fire_ice", ["#c8f6ff", "#00b4e6", "#043a66", "#000000", "#6a1500", "#f25c05", "#ffe08a"])

BODY = "#c8ccd0"   #: the body's grey
MUTED = "#6f8796"  #: the grey a wake turns to when it stops being the subject


def colormap(name: str):
    """A colour map by name: ``fire_ice`` or any matplotlib name. ``ValueError`` if unknown."""
    if name == "fire_ice":
        return FIRE_ICE
    import matplotlib
    try:
        return matplotlib.colormaps[name]
    except KeyError:
        raise ValueError(f"unknown colormap {name!r}; use fire_ice or a matplotlib name") from None


def smoothstep(value, start: float, end: float):
    """0 below ``start``, 1 above ``end``, smooth between (works on arrays)."""
    import numpy as np
    t = np.clip((np.asarray(value, dtype=float) - start) / (end - start), 0, 1)
    return t * t * (3 - 2 * t)
