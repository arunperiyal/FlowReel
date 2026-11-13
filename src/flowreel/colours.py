"""Colour maps and colours shared by the layers."""
from __future__ import annotations

from matplotlib.colors import LinearSegmentedColormap

#: Diverging map that is black at zero, so weak flow fades into a black background:
#: ice blue for negative values, fire for positive (the prototype's).
FIRE_ICE = LinearSegmentedColormap.from_list(
    "fire_ice", ["#c8f6ff", "#00b4e6", "#043a66", "#000000", "#6a1500", "#f25c05", "#ffe08a"])

BODY = "#c8ccd0"   #: the body's grey
MUTED = "#6f8796"  #: the grey a wake turns to when it stops being the subject
