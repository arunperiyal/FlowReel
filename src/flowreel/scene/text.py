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
