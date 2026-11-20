"""Text drawn in a frame by VTK, in the bundled Lato (plan Section 18).

Captions and maths come with the film (Phase 4, matplotlib). This is for the few words a
shot draws into its own frames, such as the note of a ``stretch``: VTK's text actor
with Lato's font file, so it matches the film's text.
"""
from __future__ import annotations

from pathlib import Path

import flowreel

FONTS = Path(flowreel.__file__).parent / "fonts"
MARGIN = 0.02            # of the picture's height, from the frame's edges


def font_file(style: str = "Regular") -> str:
    """The path of the bundled ``Lato-<style>.ttf``."""
    return str(FONTS / f"Lato-{style}.ttf")


def corner_text(plotter, text: str, corner: str, size: float, colour, picture: tuple[int, int]):
    """Write ``text`` in ``corner`` (``lower_left`` ...) of a picture ``picture``
    (width, height) pixels, ``size`` pixels high, in ``colour``. Returns the actor."""
    from flowreel.tracks import parse_colour
    width, height = picture
    pad = MARGIN * height
    x = pad if corner.endswith("left") else width - pad
    y = pad if corner.startswith("lower") else height - pad - size
    actor = plotter.add_text(text, position=(x, y), font_size=max(int(round(size)), 1),
                             color=parse_colour(colour) if isinstance(colour, str) else colour,
                             font_file=font_file())
    prop = actor.GetTextProperty()
    prop.SetFontSize(max(int(round(size)), 1))     # pyvista doubles the size it is given
    prop.SetJustificationToLeft() if corner.endswith("left") else prop.SetJustificationToRight()
    return actor


def lato(prop, size: float, colour, opacity: float = 1.0, bold: bool = False):
    """Set a ``vtkTextProperty`` to the bundled Lato through VTK's font-file option,
    ``size`` pixels high, in ``colour`` (``#rrggbb`` or an RGB triple of 0..1).
    Returns ``prop``."""
    from vtkmodules.vtkCommonCore import VTK_FONT_FILE

    from flowreel.tracks import parse_colour
    prop.SetFontFamily(VTK_FONT_FILE)
    prop.SetFontFile(font_file("Bold" if bold else "Regular"))
    prop.SetFontSize(max(int(round(size)), 1))
    prop.SetColor(*(parse_colour(colour) if isinstance(colour, str) else colour))
    prop.SetOpacity(opacity)
    prop.SetJustificationToCentered()
    prop.SetVerticalJustificationToCentered()
    return prop


def to_display(renderer, point) -> tuple[float, float, float]:
    """Where model ``point`` falls in the window, in pixels from the lower left, and its
    depth (0 near .. 1 far; outside that range it is not in view), through
    ``renderer``'s camera and viewport, where a shot's stretch draws it
    (:mod:`flowreel.scene.drawn`)."""
    from vtkmodules.vtkRenderingCore import vtkCoordinate

    from flowreel.scene.drawn import to_drawn
    point = to_drawn(renderer, point)
    c = vtkCoordinate()
    c.SetCoordinateSystemToWorld()
    c.SetValue(*(float(v) for v in point))
    x, y = c.GetComputedDoubleDisplayValue(renderer)
    renderer.SetWorldPoint(*(float(v) for v in point), 1.0)
    renderer.WorldToDisplay()
    return x, y, renderer.GetDisplayPoint()[2]


def label_at(renderer, text: str, point, size: float, colour, opacity: float = 1.0,
             offset=(0.0, 0.0)):
    """A label in Lato, ``size`` pixels high, centred where model ``point`` falls in
    ``renderer``'s view, moved ``offset`` pixels (right, up). Returns the actor (a 2D
    ``vtkTextActor``, added to ``renderer``), or ``None`` when the point is behind the
    camera.

    The label is placed once, for the camera as it is when this is called, so call it
    after the frame's camera is set. It is drawn over the model, never hidden by it:
    labels of axes stay readable.
    """
    from vtkmodules.vtkRenderingCore import vtkTextActor
    x, y, depth = to_display(renderer, point)
    if not 0 <= depth <= 1:
        return None
    actor = vtkTextActor()
    actor.SetInput(text)
    actor.SetTextScaleModeToNone()
    actor.GetPositionCoordinate().SetCoordinateSystemToDisplay()
    actor.SetPosition(x + offset[0], y + offset[1])
    lato(actor.GetTextProperty(), size, colour, opacity)
    renderer.AddViewProp(actor)       # AddActor2D is gone from VTK 9.7
    return actor
