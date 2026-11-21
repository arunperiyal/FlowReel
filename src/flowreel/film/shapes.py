"""2D shapes on the frame (plan Section 12): arrows, lines, boxes and the like.

A caption's ``shapes`` is a list, one shape per entry, written as ``{kind: {keys}}``:

.. code-block:: yaml

    shapes:
      - {arrow: {from: [1395, 445], to: [1300, 462], width: 4}}
      - {box: {from: [900, 300], to: [1200, 520], radius: 8}}
      - {dimension: {from: [700, 800], to: [900, 800], value: '$0.2D$', offset: 30}}
      - {highlight: {from: [880, 280], to: [1220, 540], dim: 0.6}}

Points are ``[x, y]`` in pixels of the film, ``(0, 0)`` at the upper left, ``y`` down.
Widths, radii and sizes are pixels. A shape is drawn in its caption's colour unless it
gives ``colour``, and fades in and out with the caption.

"Left" below means the left of the direction ``from`` to ``to``: for a shape drawn from
left to right across the frame, its left is up. ``bracket``'s ``depth`` and
``dimension``'s ``offset`` are measured that way, so a positive value puts the bracket's
tips and the dimension's line above a horizontal shape drawn left to right.

A shape's ``from``, ``to`` and ``centre`` may instead be points in the model,
``{model: [x, y, z], offset: [dx, dy]}``, projected on every frame so the shape follows
the camera (:mod:`flowreel.film.anchors`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from flowreel.scene.errors import Checker

#: Each shape's keys; the first ones listed in ``REQUIRED`` must be given.
KEYS = {
    "arrow": ("from", "to", "width", "head", "colour"),
    "line": ("from", "to", "width", "colour"),
    "box": ("from", "to", "width", "radius", "fill", "colour"),
    "circle": ("centre", "radius", "width", "fill", "colour"),
    "ellipse": ("centre", "radii", "width", "fill", "colour"),
    "bracket": ("from", "to", "depth", "width", "colour"),
    "dimension": ("from", "to", "value", "offset", "width", "head", "size", "colour"),
    "highlight": ("from", "to", "dim", "radius"),
}
REQUIRED = {
    "arrow": ("from", "to"), "line": ("from", "to"), "box": ("from", "to"),
    "circle": ("centre", "radius"), "ellipse": ("centre", "radii"),
    "bracket": ("from", "to"), "dimension": ("from", "to"), "highlight": ("from", "to"),
}
WIDTH = 4.0                # pixels, of lines and outlines
HEAD = 4.5                 # an arrow head's length, times the line's width
DIMENSION_WIDTH = 2.0      # pixels, a dimension's lines
DIMENSION_HEAD = 14.0      # pixels, a dimension's arrow heads
BRACKET_DEPTH = 20.0       # pixels, from a bracket's back to its tips
HIGHLIGHT_DIM = 0.6        # how dark outside a highlight: 0 not at all, 1 black


@dataclass(frozen=True)
class Shape:
    """One 2D shape: ``kind`` (a key of :data:`KEYS`) and its ``keys`` checked, points
    as ``(x, y)`` tuples, numbers as floats; ``colour`` ``None`` takes the caption's."""

    kind: str
    keys: dict = field(default_factory=dict)

    def __getitem__(self, name):
        return self.keys[name]

    def get(self, name, default=None):
        """The value of key ``name``, or ``default`` when it is not given."""
        return self.keys.get(name, default)


def parse_shape(spec, check: Checker) -> Shape:
    """One shape as written, ``{kind: {keys}}``; errors name the key path."""
    from flowreel.compose.style import colour
    if not isinstance(spec, dict) or len(spec) != 1:
        raise check.error(f"expected one shape as {{name: {{...}}}}, such as "
                          f"{{arrow: {{from: [x, y], to: [x, y]}}}}; shapes: {', '.join(KEYS)}")
    check.mapping(spec, tuple(KEYS))
    (kind, value), = spec.items()
    at = check.at(kind)
    if not isinstance(value, dict):
        raise at.error("expected a mapping of the shape's keys")
    value = at.mapping(value, KEYS[kind], required=REQUIRED[kind])
    keys = {}
    for name, v in value.items():
        c = at.at(name)
        if name in ("from", "to", "centre"):
            keys[name] = _point(v, c)
        elif name == "radii":
            if isinstance(v, dict):
                raise c.error("radii are two lengths in pixels, [rx, ry]")
            keys[name] = _point(v, c)
        elif name in ("colour", "fill"):
            keys[name] = None if v is None and name == "fill" else colour(v, c)
        elif name == "value":
            keys[name] = c.string(str(v) if isinstance(v, (int, float)) else v)
        elif name in ("depth", "offset"):
            keys[name] = c.number(v)
        elif name == "dim":
            keys[name] = c.number(v)
            if not 0 <= keys[name] <= 1:
                raise c.error(f"expected 0 to 1, got {keys[name]:g}")
        else:
            keys[name] = c.number(v)
            if keys[name] < 0 or (keys[name] == 0 and name != "radius"):
                raise c.error(f"must be positive, got {keys[name]:g}")
    if "from" in keys and keys["from"] == keys["to"]:
        raise at.at("to").error("must differ from 'from'")
    return Shape(kind, keys)


def _point(value, check: Checker):
    """``[x, y]`` in pixels, or a point in the model (:class:`~flowreel.film.anchors.Anchor`)."""
    if isinstance(value, dict):
        from flowreel.film.anchors import parse_anchor
        return parse_anchor(value, check)
    x, y = check.numbers(value, 2)
    return (float(x), float(y))


def parse_all(shapes, colour: str) -> list[Shape]:
    """``shapes`` (parsed :class:`Shape` objects) with the caption's ``colour`` filled
    in where a shape names none (highlights have no colour)."""
    out = []
    for s in shapes:
        if s.kind != "highlight" and s.get("colour") is None:
            s = Shape(s.kind, {**s.keys, "colour": colour})
        out.append(s)
    return out


def _rgba(colour: str, alpha: int = 255) -> tuple[int, int, int, int]:
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(colour)
    return (round(r * 255), round(g * 255), round(b * 255), alpha)


def _along(a, b):
    """The unit vector from ``a`` to ``b`` and its left normal, as complex numbers."""
    d = complex(*b) - complex(*a)
    u = d / abs(d)
    return u, u * -1j          # y is down, so turning left is multiplying by -i


def _xy(z: complex) -> tuple[float, float]:
    return (z.real, z.imag)


def arrow(draw, start, end, colour, width: float, head: float | None = None) -> None:
    """A straight arrow from ``start`` to ``end`` with a filled head at ``end``,
    ``head`` pixels long (default 4.5 widths) and half as wide."""
    start, end = complex(*start), complex(*end)
    along = (end - start) / abs(end - start)
    head = HEAD * width if head is None else head
    base = end - head * along
    side = along * 1j * head * 0.5
    draw.line([_xy(start), _xy(base)], fill=colour, width=round(width))
    draw.polygon([_xy(end), _xy(base + side), _xy(base - side)], fill=colour)


def _box(a, b):
    (x0, y0), (x1, y1) = a, b
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def draw(draw, shape: Shape) -> None:
    """Draw ``shape`` with Pillow's ``draw`` (an ``ImageDraw`` of the caption's
    picture). Highlights are drawn by :func:`highlight_layer` instead."""
    k = shape.kind
    if k == "highlight":
        return
    colour = _rgba(shape["colour"])
    width = shape.get("width", DIMENSION_WIDTH if k == "dimension" else WIDTH)
    w = max(1, round(width))
    fill = None if shape.get("fill") is None else _rgba(shape["fill"])
    if k == "arrow":
        arrow(draw, shape["from"], shape["to"], colour, width, shape.get("head"))
    elif k == "line":
        draw.line([shape["from"], shape["to"]], fill=colour, width=w)
    elif k == "box":
        draw.rounded_rectangle(_box(shape["from"], shape["to"]), radius=shape.get("radius", 0),
                               outline=colour, fill=fill, width=w)
    elif k in ("circle", "ellipse"):
        (cx, cy) = shape["centre"]
        rx, ry = (shape["radius"],) * 2 if k == "circle" else shape["radii"]
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=colour, fill=fill, width=w)
    elif k == "bracket":
        a, b = complex(*shape["from"]), complex(*shape["to"])
        _, left = _along(shape["from"], shape["to"])
        tip = left * shape.get("depth", BRACKET_DEPTH)
        draw.line([_xy(a + tip), _xy(a), _xy(b), _xy(b + tip)], fill=colour, width=w,
                  joint="curve")
    elif k == "dimension":
        a, b = complex(*shape["from"]), complex(*shape["to"])
        _, left = _along(shape["from"], shape["to"])
        shift = left * shape.get("offset", 0.0)
        if shift:
            reach = shift + left * (3 * width if shape.get("offset", 0.0) > 0 else -3 * width)
            for end in (a, b):
                draw.line([_xy(end), _xy(end + reach)], fill=colour, width=w)
        a, b = a + shift, b + shift
        head = shape.get("head", DIMENSION_HEAD)
        mid = (a + b) / 2
        arrow(draw, _xy(mid), _xy(a), colour, width, head)
        arrow(draw, _xy(mid), _xy(b), colour, width, head)


def label_place(shape: Shape, size: float) -> tuple[float, float]:
    """The centre of a dimension's ``value``, in pixels: beside the middle of its line,
    on the left of the line (see the module), clear of it by about the letters' size."""
    a, b = complex(*shape["from"]), complex(*shape["to"])
    _, left = _along(shape["from"], shape["to"])
    offset = shape.get("offset", 0.0)
    side = 1 if offset >= 0 else -1
    return _xy((a + b) / 2 + left * (offset + side * 0.8 * size))


def add_labels(fig, shape: Shape, lk, picture: tuple[int, int]) -> None:
    """Add a dimension's ``value`` as text to the caption's matplotlib ``fig``, so its
    maths matches the caption's. ``lk`` is the caption's look."""
    if shape.kind != "dimension" or not shape.get("value"):
        return
    size = shape.get("size", lk.size * 0.8)
    x, y = label_place(shape, size)
    width, height = picture
    fig.text(x / width, 1 - y / height, shape["value"], fontsize=size * 72 / 100,
             color=shape["colour"], ha="center", va="center")


def highlight_layer(shape: Shape, picture: tuple[int, int]):
    """A highlight: the picture darkened outside a box, as a transparent RGBA layer the
    size of the ``picture`` (width, height)."""
    from PIL import Image, ImageDraw
    alpha = round(255 * shape.get("dim", HIGHLIGHT_DIM))
    layer = Image.new("RGBA", picture, (0, 0, 0, alpha))
    ImageDraw.Draw(layer).rounded_rectangle(_box(shape["from"], shape["to"]),
                                            radius=shape.get("radius", 0), fill=(0, 0, 0, 0))
    return layer
