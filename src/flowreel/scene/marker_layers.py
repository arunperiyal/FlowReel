"""Layers that need no flow data: ``outline``, ``glyphs``, ``markers3d``, ``geometry``
(plan Section 7.2). Options marked *track* take a number or keys (docs/tracks.md);
positions and lengths are in the source's unit, line widths in pixels.
"""
from __future__ import annotations

import inspect

import numpy as np
import pyvista as pv

from flowreel.box import Box
from flowreel.colours import colormap
from flowreel.scene.errors import Checker
from flowreel.scene.layers import Layer, Option, register
from flowreel.sources.bodies import available_bodies, get_body
from flowreel.tracks import parse as parse_track

AXES = ("x", "y", "z")


def region(spec, data, check: Checker | None = None) -> Box:
    """A box from ``domain``, ``crop`` or ``{x: [lo, hi], y: ..., z: ...}`` (numbers).

    ``domain`` is the source's bounds; ``crop`` the shot's crop (the domain when the shot
    has none).
    """
    if spec == "domain" or (spec == "crop" and data.crop is None):
        return data.source.bounds()
    if spec == "crop":
        return data.crop
    check = check or Checker()
    m = check.mapping(spec, AXES, required=AXES)
    r = [check.at(a).numbers(m[a], 2) for a in AXES]
    return Box(tuple(x[0] for x in r), tuple(x[1] for x in r))


def _check_region(spec, check: Checker) -> None:
    if spec in ("domain", "crop"):
        return
    if isinstance(spec, str):
        raise check.error(f"{spec!r} is not allowed (domain, crop, or {{x: [lo, hi], y: ..., z: ...}})")
    Box_ = check.mapping(spec, AXES, required=AXES)
    for a in AXES:
        lo, hi = check.at(a).numbers(Box_[a], 2)
        if lo >= hi:
            raise check.at(a).error(f"expected [low, high] with low < high, got [{lo:g}, {hi:g}]")


@register
class Outline(Layer):
    """The edges of a box: ``bounds`` (``domain``, ``crop`` or numbers), ``colour``,
    ``width`` (pixels) and ``opacity`` (tracks)."""

    name = "outline"
    options = (
        Option("bounds", track=False, default="domain"),
        Option("colour", "colour", default="#ffffff"),
        Option("width", "number", default=1.0),
        Option("opacity", "number", default=1.0),
    )

    @classmethod
    def check(cls, raw, check):
        _check_region(raw.get("bounds", "domain"), check.at("bounds"))

    def draw(self, plotter, frame) -> None:
        v = frame.values
        box = region(v["bounds"], frame.data)
        edges = pv.Box(bounds=box.to_bounds()).extract_all_edges()
        plotter.add_mesh(edges, color=v["colour"], line_width=v["width"],
                         opacity=v["opacity"], lighting=False)
