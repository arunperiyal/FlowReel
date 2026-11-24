"""The watermark drawn (plan Section 10.7): a signature, a logo or a line of text.

A :class:`~flowreel.film.schema.Watermark` is drawn by Pillow on a transparent picture
the size of the frame: an ``image`` scaled to ``size`` pixels high, or a line of
``text`` in the bundled Lato, ``size`` pixels being the font's size (as a caption's).
It sits in ``corner``, a margin of 2% of the picture's height from the edges (as a
shot's stretch note), or with its upper left corner at ``place``. ``opacity``
multiplies the image's own transparency.

Two levels use it:

- **Film level** (``watermark:`` in ``film.yml``): drawn at the build with the captions,
  over the scenes and seconds it names, so changing it never re-renders a
  frame.
- **Shot level** (``watermark:`` in a shot file, for frames used outside a film):
  :func:`stamp` draws it into each frame after the screenshot; its look is part of the
  frame's key, and a draft scales it with the picture.

Image files stay outside the repository (no logos in it).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from flowreel.film.schema import Watermark

MARGIN = 0.02              # of the picture's height, from the edges, in a corner


def watermark_image(w: Watermark, picture: tuple[int, int], scale: float = 1.0):
    """``w`` drawn on a transparent RGBA picture of ``picture`` (width, height) pixels.
    ``scale`` multiplies its size and ``place`` (a draft at half size: 0.5)."""
    from PIL import Image
    width, height = picture
    mark = _mark(w, scale)
    if w.place is not None:
        x, y = (round(v * scale) for v in w.place)
    else:
        pad = round(MARGIN * height)
        x = pad if w.corner.endswith("left") else width - pad - mark.width
        y = pad if w.corner.startswith("upper") else height - pad - mark.height
    layer = Image.new("RGBA", picture, (0, 0, 0, 0))
    layer.paste(mark, (x, y))          # copied as is: the layer is empty, and may clip it
    return layer


def _mark(w: Watermark, scale: float):
    """The watermark alone, cropped to its ink, with its opacity applied."""
    from matplotlib.colors import to_rgb
    from PIL import Image, ImageDraw

    from flowreel.scene.text import font_file, pillow_font
    size = max(1, round(w.size * scale))
    if w.image is not None:
        mark = Image.open(w.image).convert("RGBA")
        mark = mark.resize((max(1, round(mark.width * size / mark.height)), size), Image.LANCZOS)
    else:
        font = pillow_font(font_file(), size)
        left, top, right, bottom = font.getbbox(w.text)
        mark = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)), (0, 0, 0, 0))
        r, g, b = (round(c * 255) for c in to_rgb(w.colour))
        ImageDraw.Draw(mark).text((-left, -top), w.text, font=font, fill=(r, g, b, 255))
    if w.opacity < 1:
        a = np.asarray(mark.getchannel("A"), dtype=float) * w.opacity
        mark.putalpha(Image.fromarray(np.round(a).astype(np.uint8)))
    return mark


def stamp(picture: np.ndarray, w: Watermark, scale: float = 1.0) -> np.ndarray:
    """``picture`` (``(height, width, 3)`` uint8) with ``w`` drawn on it, scaled by
    ``scale``: a shot's watermark, drawn into each frame."""
    from PIL import Image
    height, width = picture.shape[:2]
    base = Image.fromarray(picture).convert("RGBA")
    base.alpha_composite(watermark_image(w, (width, height), scale))
    return np.asarray(base.convert("RGB"))


def key_fields(w: Watermark | None):
    """What decides a watermark's pixels, for a frame's key: its keys, and for an image
    its file's size and modification time (a logo replaced in place redraws)."""
    if w is None:
        return None
    from dataclasses import asdict
    out = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(w).items()}
    if w.image is not None:
        st = Path(w.image).stat()
        out["image_file"] = [st.st_size, st.st_mtime_ns]
    return out
