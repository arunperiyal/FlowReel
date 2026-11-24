"""One frame of a scene drawn (plan Section 19.11, Phase 10 branch 2): its layout's boxes,
each as it shows at a time.

:func:`draw_frame` draws the frame ``t`` seconds into a scene: the layout's background,
then each box that shows at ``t`` (:func:`opacity`), first at the back. What a timed box
shows at that moment, the picture of a shot, panel or held frame, is given in
:class:`Contents`: which frame of a shot shows at ``t`` (its rate and freezes) is the
scene build's to say (branch 3), as is the last frame of another scene.

- **Text** is set by matplotlib in the film's font, so ``$...$`` is mathematics, then
  given a soft shadow or a dark box as captions are (:mod:`flowreel.film.draw`). In a box
  of its own size it sits by its look's ``align`` and ``valign`` within ``margin`` of the
  edges; at ``pos`` alone (or following a point) its upper left corner is there and the
  box is as large as the text. A text box at ``pos`` in the ``text`` look draws the same
  pixels as a caption placed there.
- **Images** are fitted to the box (``contain``: all of it, centred; ``cover``: the box
  filled, the picture cut to fit; ``stretch``), at their opacity.
- **Shapes** are drawn in the box: a rectangle its outline, a circle the ellipse within it,
  a line or arrow across it (:data:`ENDS`).
- **Shot, panel and held frames** are fitted to the box, aspect kept and centred.
- **Following a point.** A text or shape box with ``follow`` is placed each frame on a
  point of the flow, projected by the camera that drew the shot box's picture
  (``Contents.views``), then carried into the shot box as its picture is: a text's upper
  left corner, an arrow's or line's end, a rectangle's or circle's centre go there, moved
  by ``offset``. A point behind the camera or off the picture hides the box on that frame.

Coordinates are the film's pixels, ``(0, 0)`` at the upper left, ``y`` down.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from flowreel.film.model import Box, Film, Look, Scene, Style

#: A line's or arrow's ends in its box for each direction: from (x, y) to (x, y), as
#: fractions of the box's width and height.
ENDS = {
    "right": ((0, 0.5), (1, 0.5)), "left": ((1, 0.5), (0, 0.5)),
    "up": ((0.5, 1), (0.5, 0)), "down": ((0.5, 0), (0.5, 1)),
    "up_right": ((0, 1), (1, 0)), "up_left": ((1, 1), (0, 0)),
    "down_right": ((0, 0), (1, 1)), "down_left": ((1, 0), (0, 1)),
}


@dataclass
class Contents:
    """What the timed boxes of a scene show on one frame: ``pictures`` by box name (a
    Pillow image, or a path to one) for shot, panel and ``last_frame`` boxes, and
    ``views`` by shot box name: the :class:`~flowreel.scene.frame_views.DrawnView` that
    drew its picture (for boxes that follow a point)."""

    pictures: dict = field(default_factory=dict)
    views: dict = field(default_factory=dict)


def colour_of(value: str | None, style: Style) -> str:
    """A look's or shape's ``colour``: ``None`` is the film's text colour, ``muted`` its
    muted one."""
    if value is None:
        return style.text
    return style.muted if value == "muted" else value


def opacity(box: Box, t: float, length: float) -> float:
    """How much of ``box`` shows ``t`` seconds into a scene ``length`` seconds long, 0 to
    1: inside its ``at`` (the whole scene without one), faded in and out by its ``fade``
    (a text's look's fade when it gives none and has ``at``)."""
    start, end = (0.0, length) if box.at is None else (box.at[0], length if box.at[1] is None
                                                         else box.at[1])
    if t < start - 1e-9 or t > end + 1e-9:
        return 0.0
    fade = box.fade
    if fade is None and box.at is not None and box.kind == "text":
        f = box.content.drawn.fade
        fade = (f, f)
    if fade is None:
        return 1.0
    a = 1.0
    if fade[0] > 0:
        a = min(a, (t - start) / fade[0])
    if fade[1] > 0:
        a = min(a, (end - t) / fade[1])
    return float(min(max(a, 0.0), 1.0))


# ---- fitting pictures ---------------------------------------------------------------

def _open(picture):
    from PIL import Image
    if isinstance(picture, (str, Path)):
        with Image.open(picture) as im:
            return im.convert("RGBA")
    return picture.convert("RGBA")


def fitted(picture, rect, fit: str = "contain"):
    """``picture`` (a Pillow image or a file) fitted to ``rect`` ``(x, y, w, h)``:
    ``(image, (left, top))``, the image resized (and for ``cover`` cut) and where its
    upper left corner goes."""
    from PIL import Image
    im = _open(picture)
    x, y, w, h = rect
    W, H = max(round(w), 1), max(round(h), 1)
    if fit == "stretch":
        return im.resize((W, H), Image.LANCZOS), (round(x), round(y))
    s = (min if fit == "contain" else max)(W / im.width, H / im.height)
    iw, ih = max(round(im.width * s), 1), max(round(im.height * s), 1)
    im = im.resize((iw, ih), Image.LANCZOS)
    if fit == "cover":
        left, top = (iw - W) // 2, (ih - H) // 2
        return im.crop((left, top, left + W, top + H)), (round(x), round(y))
    return im, (round(x) + (W - iw) // 2, round(y) + (H - ih) // 2)


# ---- text ---------------------------------------------------------------------------

def text_image(lines, look: Look, style: Style, picture: tuple[int, int], *,
               rect=None, corner=None):
    """``lines`` drawn in ``look`` on a transparent picture of ``picture`` pixels:
    within ``rect`` ``(x, y, w, h)`` by the look's ``align``, ``valign`` and ``margin``,
    or with the text's upper left corner at ``corner``. Returns ``(image, (left, top,
    right, bottom))``, the text's own box."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFilter

    from flowreel.compose.style import register_fonts
    from flowreel.film.draw import BOX_ALPHA, BOX_RADIUS, SHADOW_BLUR, SHADOW_GROW, _figure
    from flowreel.film.draw import maths_settings
    register_fonts()
    width, height = picture
    colour = colour_of(look.colour, style)
    weight = {"bold": "bold", "light": "light"}.get(look.weight, "normal")
    fstyle = "italic" if look.weight == "italic" else "normal"
    with mpl.rc_context(maths_settings(style)):
        fig = _figure(picture)
        try:
            points = look.size * 72 / 100       # letter height in pixels to points at 100 dpi
            texts = [fig.text(0, 1, line, fontsize=points, color=colour, va="top",
                              fontweight=weight, fontstyle=fstyle) for line in lines]
            renderer = fig.canvas.get_renderer()
            widths = [float(t.get_window_extent(renderer).width) for t in texts]
            spacing = round(look.size * look.spacing)
            wide, tall = max(widths), spacing * len(texts)
            if rect is not None:
                x, y, w, h = rect
                m = look.margin
                left = {"left": x + m, "centre": x + (w - wide) / 2,
                        "right": x + w - m - wide}[look.align]
                top = {"top": y + m, "centre": y + (h - tall) / 2,
                       "bottom": y + h - m - tall}[look.valign]
            else:
                left, top = corner
            for i, (t, w) in enumerate(zip(texts, widths)):
                lx = {"left": left, "centre": left + (wide - w) / 2,
                      "right": left + wide - w}[look.align]
                t.set_position((lx / width, 1 - (top + i * spacing) / height))
            fig.canvas.draw()
            words = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy())
        finally:
            plt.close(fig)
    block = (left, top, left + wide, top + tall)
    back = Image.new("RGBA", picture, (0, 0, 0, 0))
    if look.box:
        pad = round(look.size * 0.6)
        ImageDraw.Draw(back).rounded_rectangle(
            (left - pad, top - pad * 0.7, left + wide + pad, top + tall + pad * 0.3),
            radius=BOX_RADIUS, fill=(0, 0, 0, BOX_ALPHA))
    elif look.shadow:
        back.putalpha(words.getchannel("A").filter(ImageFilter.MaxFilter(SHADOW_GROW))
                      .filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))
    return Image.alpha_composite(back, words), block


# ---- shapes -------------------------------------------------------------------------

def shape_image(shape, rect, style: Style, picture: tuple[int, int]):
    """A shape box's ``shape`` drawn in ``rect`` on a transparent picture."""
    from PIL import Image, ImageDraw

    from flowreel.film.shapes import _rgba, arrow
    out = Image.new("RGBA", picture, (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    x, y, w, h = rect
    colour = _rgba(colour_of(shape.colour, style))
    width = round(shape.width)
    if shape.kind in ("rectangle", "circle"):
        fill = None if shape.fill is None else _fill(shape.fill)
        box = (x, y, x + w - 1, y + h - 1)
        if shape.kind == "rectangle":
            draw.rounded_rectangle(box, radius=shape.radius, outline=colour, width=width,
                                   fill=fill)
        else:
            draw.ellipse(box, outline=colour, width=width, fill=fill)
        return _shadowed(out) if shape.shadow else out
    (fx, fy), (tx, ty) = ENDS[shape.direction]
    a = (x + fx * (w - 1), y + fy * (h - 1))
    b = (x + tx * (w - 1), y + ty * (h - 1))
    if shape.kind == "arrow":
        arrow(draw, a, b, colour, shape.width, shape.head)
    else:
        draw.line([a, b], fill=colour, width=width)
    return _shadowed(out) if shape.shadow else out


def _shadowed(image):
    """``image`` over a soft shadow of itself, as a caption's text has."""
    from PIL import Image, ImageFilter

    from flowreel.film.draw import SHADOW_BLUR, SHADOW_GROW
    back = Image.new("RGBA", image.size, (0, 0, 0, 0))
    back.putalpha(image.getchannel("A").filter(ImageFilter.MaxFilter(SHADOW_GROW))
                  .filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))
    return Image.alpha_composite(back, image)


def _fill(value: str) -> tuple[int, int, int, int]:
    """A fill colour, with its alpha when written ``#rrggbbaa``."""
    from flowreel.film.shapes import _rgba
    if isinstance(value, str) and value.startswith("#") and len(value) == 9:
        return (*_rgba(value[:7])[:3], int(value[7:], 16))
    return _rgba(value)


# ---- following a point --------------------------------------------------------------

def follow_point(box: Box, layout, contents: Contents, film_size) -> tuple[float, float] | None:
    """Where ``box``'s point is in the film this frame (offset added), or ``None`` when
    it is hidden or the shot box shows nothing."""
    from flowreel.film.anchors import fitting
    f = box.follow
    view = contents.views.get(f.box)
    if view is None:
        return None
    x, y, depth = view.pixels(f.model)[0]
    w, h = view.size
    if not (np.isfinite(x) and np.isfinite(y)) or depth <= 0 or not (0 <= x <= w and 0 <= y <= h):
        return None
    rx, ry, rw, rh = layout.box(f.box).rect(film_size)
    sx, sy, ox, oy = fitting(view.size, (round(rw), round(rh)))
    return (rx + x * sx + ox + f.offset[0], ry + y * sy + oy + f.offset[1])


def anchored_rect(box: Box, point) -> tuple[float, float, float, float]:
    """The rectangle of a shape box that follows ``point``: an arrow's or line's end on
    it, a rectangle's or circle's centre."""
    w, h = box.size
    if box.content.kind in ("line", "arrow"):
        fx, fy = ENDS[box.content.direction][1]
        return (point[0] - fx * (w - 1), point[1] - fy * (h - 1), w, h)
    return (point[0] - w / 2, point[1] - h / 2, w, h)


# ---- one frame ----------------------------------------------------------------------

def box_image(box: Box, film: Film, layout, contents: Contents):
    """``box`` drawn on a transparent picture of the film's size (before its opacity),
    or ``None`` when it shows nothing on this frame (a hidden point, no picture)."""
    from PIL import Image
    size = film.size
    kind = box.kind
    point = None
    if box.follow is not None:
        point = follow_point(box, layout, contents, size)
        if point is None:
            return None
    if kind == "text":
        rect = box.rect(size)
        corner = point if point is not None else box.pos
        image, _ = text_image(box.content.lines, box.content.drawn, film.style, size,
                              rect=rect if point is None else None, corner=corner)
        return image
    if kind == "shape":
        rect = anchored_rect(box, point) if point is not None else box.rect(size)
        return shape_image(box.content, rect, film.style, size)
    rect = box.rect(size)
    if kind == "image":
        im, at = fitted(box.content.file, rect, box.content.fit)
        out = Image.new("RGBA", size, (0, 0, 0, 0))
        out.paste(im, at, im)
        if box.content.opacity < 1:
            a = np.asarray(out.getchannel("A"), float) * box.content.opacity
            out.putalpha(Image.fromarray(a.round().astype(np.uint8)))
        return out
    picture = contents.pictures.get(box.name)
    if picture is None:
        return None
    im, at = fitted(picture, rect, "contain")
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(im, at, im)
    return out


def scene_length(scene: Scene, length: float | None) -> float:
    """A scene's length: its ``seconds``, else ``length`` as given (its main box's)."""
    if scene.seconds is not None:
        return scene.seconds
    if length is None:
        raise ValueError(f"scene {scene.name!r} lasts as its main box: give its length")
    return length


def still(box: Box) -> bool:
    """Whether ``box`` looks the same on every frame but for its opacity: text, an image
    or a shape that follows no point (its picture can be drawn once a scene)."""
    return box.kind in ("text", "image", "shape") and box.follow is None


def draw_frame(film: Film, scene: Scene, t: float, contents: Contents | None = None,
               length: float | None = None, cache: dict | None = None):
    """The frame ``t`` seconds into ``scene``: a Pillow RGB image of the film's size.
    ``length`` is the scene's length when it has no ``seconds`` (its main box's frames,
    freezes included). ``cache`` (a dict kept across the frames of one scene) keeps the
    pictures of :func:`still` boxes, drawn once instead of on every frame."""
    from PIL import Image
    from matplotlib.colors import to_rgb
    contents = contents or Contents()
    total = scene_length(scene, length)
    layout = scene.layout
    rgb = tuple(round(c * 255) for c in to_rgb(layout.background))
    frame = Image.new("RGBA", film.size, (*rgb, 255))
    for box in layout.boxes:
        a = opacity(box, t, total)
        if a <= 0:
            continue
        if cache is not None and still(box):
            if box.name not in cache:
                cache[box.name] = box_image(box, film, layout, contents)
            image = cache[box.name]
            image = None if image is None else image.copy()
        else:
            image = box_image(box, film, layout, contents)
        if image is None:
            continue
        if a < 1:
            alpha = np.asarray(image.getchannel("A"), float) * a
            image.putalpha(Image.fromarray(alpha.round().astype(np.uint8)))
        frame = Image.alpha_composite(frame, image)
    return frame.convert("RGB")


# ---- shots and panels ---------------------------------------------------------------

def shot_frames(box: Box) -> Path:
    """The folder of a shot box's frames: its ``frames``, or its shot's
    ``frames/<name>`` under the project (:func:`flowreel.project.paths.output`)."""
    content = box.content
    if content.frames is not None:
        return content.frames
    from flowreel.project.paths import output
    from flowreel.scene.shot import load
    shot = load(content.file)
    return output(content.file, "frames") / shot.name


class PanelDrawer:
    """A panel box's pictures: its panel file drawn at ``size`` (the box's), the figure
    built once, a picture at any time (:meth:`at`)."""

    def __init__(self, file: str | Path, size: tuple[int, int]):
        from flowreel.compose.panel_file import load
        from flowreel.compose.panels import make
        pf = load(file)
        self.panel = dataclasses.replace(pf, size=(int(size[0]), int(size[1])))
        self.kind = make(self.panel)
        self._canvas = None

    def at(self, time: float):
        """The panel at ``time`` (in its source's time unit): a Pillow RGB image."""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from PIL import Image

        from flowreel.compose.panels import DPI
        pf = self.panel
        with pf.style.applied():
            if self._canvas is None:
                figure = Figure(figsize=(pf.size[0] / DPI, pf.size[1] / DPI), dpi=DPI)
                self._canvas = FigureCanvasAgg(figure)
                figure.patch.set_facecolor(pf.style.background)
                self.kind.build(figure)
            self.kind.update(time)
            self._canvas.draw()
            return Image.frombuffer("RGBA", self._canvas.get_width_height(),
                                    self._canvas.buffer_rgba(), "raw", "RGBA", 0, 1).convert("RGB")


def follow_points(film: Film, shot_name: str | None = None) -> list[tuple[str, tuple]]:
    """The points of the flow that boxes of ``film`` follow, as ``(label, model)``: of
    shot boxes showing the shot called ``shot_name`` (every shot box when ``None``). The
    label is a text box's first line, else the box's name (for the camera editor)."""
    from flowreel.scene.shot import load
    names: dict = {}
    out = []
    for scene in film.scenes:
        layout = scene.layout
        for box in layout.boxes:
            if box.follow is None:
                continue
            shot = layout.box(box.follow.box).content
            if shot.file is None:
                continue
            if shot.file not in names:
                try:
                    names[shot.file] = load(shot.file).name
                except Exception:                       # a shot that does not load
                    names[shot.file] = None
            if shot_name is not None and names[shot.file] != shot_name:
                continue
            label = box.content.lines[0] if box.kind == "text" else box.name
            point = (label, box.follow.model)
            if point not in out:
                out.append(point)
    return out
