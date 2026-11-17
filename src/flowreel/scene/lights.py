"""Lights (plan Section 7.4): the default kit, ``raking``, or a list.

A light is either a *headlight* (moves with the camera, ``direction`` is ignored) or a
*scene* light fixed in the model with a ``direction`` it shines **from** (a vector from
the focal point towards the light). ``intensity`` is 0 to 1 or more, ``colour`` an sRGB
triple. ``specular`` is the weight of the highlight.

* ``default``: a headlight (0.8) and a soft fill from above-left (0.3): even, flat.
* ``raking``: a strong side light (1.0, along +x, nearly grazing the surface so grooves
  and ridges cast shading) and a weak headlight (0.15).
* a list of ``{kind: head|scene, direction: [x,y,z], intensity: n, colour: c}``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flowreel.scene.errors import Checker
from flowreel.tracks import parse_colour

KINDS = ("head", "scene")
PRESETS = ("default", "raking")


@dataclass(frozen=True)
class Light:
    """One light. See the module docstring for the fields."""

    kind: str = "head"
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    intensity: float = 1.0
    colour: tuple[float, float, float] = (1.0, 1.0, 1.0)
    specular: float = 0.3


KITS = {
    "default": (Light("head", intensity=0.8), Light("scene", (-0.4, 0.8, 0.4), 0.3, specular=0.0)),
    "raking": (Light("scene", (1.0, 0.1, 0.0), 1.0, specular=0.5),
               Light("head", intensity=0.15, specular=0.0)),
}


def parse_lights(spec, check: Checker | None = None) -> tuple[Light, ...]:
    """Lights from ``default``, ``raking`` or a list of mappings."""
    check = check or Checker(None, ("lights",))
    if isinstance(spec, str):
        return KITS[check.choice(spec, PRESETS)]
    out = []
    for i, item in enumerate(check.sequence(spec, 1)):
        where = check.at(i)
        item = where.mapping(item, ("kind", "direction", "intensity", "colour", "specular"))
        kind = where.at("kind").choice(item.get("kind", "head"), KINDS)
        d = where.at("direction").numbers(item.get("direction", (0, 0, 1)), 3)
        if kind == "scene" and not np.linalg.norm(d):
            raise where.at("direction").error("a scene light needs a non-zero direction")
        inten = where.at("intensity").number(item.get("intensity", 1.0))
        spec_w = where.at("specular").number(item.get("specular", 0.3))
        if inten < 0 or spec_w < 0:
            raise where.error("intensity and specular cannot be negative")
        try:
            colour = parse_colour(item.get("colour", "#ffffff"))
        except ValueError as exc:
            raise where.at("colour").wrap(exc) from None
        out.append(Light(kind, d, inten, colour, spec_w))
    return tuple(out)


def apply_lights(plotter, lights, view) -> None:
    """Replace the plotter's lights by ``lights`` for the camera ``view``.

    Scene lights sit at ``focal + direction * distance``; headlights are camera lights.
    """
    import pyvista as pv
    plotter.remove_all_lights()
    for lt in lights:
        d = np.asarray(lt.direction, float)
        if lt.kind == "head":
            light = pv.Light(light_type="headlight")
        else:
            light = pv.Light(position=tuple(np.asarray(view.focal) + d / np.linalg.norm(d) * view.distance),
                             focal_point=view.focal, light_type="scene light")
        light.intensity = lt.intensity
        light.diffuse_color = lt.colour
        light.specular_color = (1, 1, 1)
        plotter.add_light(light)
