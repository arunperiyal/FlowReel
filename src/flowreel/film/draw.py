"""Captions drawn (plan Section 10.4): one transparent picture per caption.

The words are set by matplotlib in the film's font (the bundled Lato), so text between
``$`` is mathematics in a matching font. Each line is measured after it is drawn and
placed by its measured width, so centring, alignment and a box fit the text as it
appears, not an estimate. Behind the text is either a soft shadow (the text's outline
widened and blurred) or a dark box with rounded corners; with ``box`` the box takes the
shadow's place. The caption's 2D shapes (:mod:`flowreel.film.shapes`) are drawn on the
same picture, in the caption's colour unless they name one, and share its shadow.

Coordinates are pixels of the film, ``(0, 0)`` at the upper left, ``y`` down. A
caption's ``size`` is the height of its letters in pixels (matplotlib's font size in
points at 100 dots per inch, times 100/72); lines are ``spacing`` times the size apart.

:func:`caption_image` draws one caption; :func:`text_block` only measures, so other
code (a contact sheet, a check of a caption's place) can know where text falls without
drawing it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flowreel.film.schema import FilmStyle
from flowreel.film.text import Caption

BOX_ALPHA = 175            # of 255, the dark box behind boxed text
BOX_RADIUS = 12            # pixels
SHADOW_GROW = 9            # pixels, the text's outline widened by this (an odd size)
SHADOW_BLUR = 12           # pixels, Gaussian blur of the widened outline


@dataclass(frozen=True)
class Look:
    """A caption's look, its gaps filled from the film's style: letter ``size`` in
    pixels, ``colour``, ``align`` of its lines, ``box`` or ``shadow`` behind, line
    ``spacing`` (times the size) and the ``margin`` of ``top`` and ``bottom`` places."""

    size: float
    colour: str
    align: str
    box: bool
    shadow: bool
    spacing: float
    margin: float


def look(caption: Caption, style: FilmStyle) -> Look:
    """The :class:`Look` of ``caption``: its own values, else ``style``'s."""
    cs = style.caption

    def given(value, default):
        return default if value is None else value

    return Look(size=given(caption.size, cs.size), colour=given(caption.colour, style.text),
                align=given(caption.align, cs.align), box=given(caption.box, cs.box),
                shadow=given(caption.shadow, cs.shadow), spacing=cs.spacing,
                margin=cs.margin)


@dataclass(frozen=True)
class Block:
    """Where a caption's text falls: its box ``(left, top, right, bottom)`` in pixels,
    each line's ``(x, y)`` upper left corner and its measured width."""

    box: tuple[float, float, float, float]
    lines: tuple[tuple[float, float], ...]
    widths: tuple[float, ...]


def maths_settings(style: FilmStyle) -> dict:
    """matplotlib's settings for text in ``style``: the font, and the maths font set
    (``font``: the text's own font, upright, italic and bold, as the AFMS film)."""
    family = style.font
    rc = {"font.family": [family, "DejaVu Sans"]}
    if style.maths == "font":
        rc.update({"mathtext.fontset": "custom", "mathtext.rm": family,
                   "mathtext.it": f"{family}:italic", "mathtext.bf": f"{family}:bold"})
    else:
        rc["mathtext.fontset"] = style.maths
    return rc


def _figure(picture: tuple[int, int]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    width, height = picture
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0)
    return fig


def _layout(texts, renderer, caption: Caption, lk: Look, picture) -> Block:
    """Measure the drawn ``texts`` and place them (see :class:`Block`)."""
    width, height = picture
    widths = [float(t.get_window_extent(renderer).width) for t in texts]
    spacing = round(lk.size * lk.spacing)
    wide = max(widths)
    tall = spacing * len(texts)
    place = caption.place
    if isinstance(place, tuple):
        left, top = place
        if left == "centre":
            left = (width - wide) / 2
    else:
        left = (width - wide) / 2
        top = {"top": lk.margin, "centre": (height - tall) / 2,
               "bottom": height - lk.margin - tall}[place]
    lines = []
    for i, w in enumerate(widths):
        x = {"left": left, "centre": left + (wide - w) / 2, "right": left + wide - w}[lk.align]
        lines.append((x, top + i * spacing))
    return Block((left, top, left + wide, top + tall), tuple(lines), tuple(widths))


def _set_text(fig, caption: Caption, lk: Look):
    points = lk.size * 72 / 100      # letter height in pixels to points at 100 dpi
    return [fig.text(0, 1, line, fontsize=points, color=lk.colour, va="top")
            for line in caption.lines]


def text_block(caption: Caption, style: FilmStyle, picture: tuple[int, int]) -> Block:
    """Where ``caption``'s text falls in a picture of ``picture`` (width, height)
    pixels, without drawing it."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    from flowreel.compose.style import register_fonts
    register_fonts()
    lk = look(caption, style)
    with mpl.rc_context(maths_settings(style)):
        fig = _figure(picture)
        try:
            return _layout(_set_text(fig, caption, lk), fig.canvas.get_renderer(), caption,
                           lk, picture)
        finally:
            plt.close(fig)


def caption_image(caption: Caption, style: FilmStyle, picture: tuple[int, int],
                  text: bool = True):
    """``caption`` drawn on a transparent picture of ``picture`` (width, height)
    pixels: its text, its shapes, and its shadow or box. ``text`` false leaves out the
    words and their box, keeping the shapes (an anchored caption whose place is hidden
    on this frame). Returns ``(image, block)``, a Pillow RGBA image and the text's
    :class:`Block`."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFilter

    from flowreel.compose.style import register_fonts
    from flowreel.film import shapes as shapes_mod
    register_fonts()
    lk = look(caption, style)
    width, height = picture
    parsed = shapes_mod.parse_all(caption.shapes, lk.colour)
    with mpl.rc_context(maths_settings(style)):
        fig = _figure(picture)
        try:
            texts = _set_text(fig, caption, lk)
            block = _layout(texts, fig.canvas.get_renderer(), caption, lk, picture)
            for t, (x, y) in zip(texts, block.lines):
                t.set_position((x / width, 1 - y / height))
                t.set_visible(text)
            for shape in parsed:
                shapes_mod.add_labels(fig, shape, lk, picture)
            fig.canvas.draw()
            words = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy())
        finally:
            plt.close(fig)
    draw = ImageDraw.Draw(words)
    for shape in parsed:
        shapes_mod.draw(draw, shape)
    back = Image.new("RGBA", picture, (0, 0, 0, 0))
    if lk.box and text:
        left, top, right, bottom = block.box
        pad = round(lk.size * 0.6)
        ImageDraw.Draw(back).rounded_rectangle(
            (left - pad, top - pad * 0.7, right + pad, bottom + pad * 0.3),
            radius=BOX_RADIUS, fill=(0, 0, 0, BOX_ALPHA))
    elif lk.shadow:
        back.putalpha(words.getchannel("A").filter(ImageFilter.MaxFilter(SHADOW_GROW))
                      .filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))
    for shape in parsed:
        if shape.kind == "highlight":
            back = Image.alpha_composite(shapes_mod.highlight_layer(shape, picture), back)
    return Image.alpha_composite(back, words), block


def save_caption(caption: Caption, style: FilmStyle, picture: tuple[int, int], path,
                 text: bool = True) -> None:
    """Draw ``caption`` (:func:`caption_image`) and save it as a PNG at ``path``."""
    image, _ = caption_image(caption, style, picture, text)
    image.save(path)
