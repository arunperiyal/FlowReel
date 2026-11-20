"""Cards (plan Section 10.5): a still made of blocks placed down a background.

The opening and end cards of a film are files, not code, so a different competition's
layout is a different file:

.. code-block:: yaml

    # cards/opening.yml
    background: black
    blocks:
      - {image: ../assets/logo.png, height: 190, y: 110}
      - {title: ['Effect of Helical Grooves', 'on Vortex-Induced Vibration'],
         size: 60, spacing: 82, gap: 70}
      - {divider: 320, gap: 38}
      - {heading: CREATED BY, names: ['A. Author'], gap: 46}
      - {heading: CO-AUTHORED BY, names: ['B. Author, C. Author'], gap: 26}
      - {text: ['Made with FlowReel'], gap: 60}

Each block is one of ``image``, ``title``, ``divider``, ``names`` (with an optional
``heading``) or ``text`` (small print), centred across the card by its measured width.
Its top is ``y`` pixels from the card's top, or ``gap`` pixels below the end of the
block before it. Each block's height is what it draws: an image's height, lines times
their ``spacing``, a divider's ``thickness``, a heading's ``heading_gap`` plus the names.

Sizes, spacing and positions are pixels of a card ``size`` pixels large (default 1920 by
1080, the size the card is written for); drawn at another size, the whole card is
scaled. Text is the bundled Lato (``weight``: ``regular``, ``light``, ``bold`` or
``italic``), drawn by Pillow, unless the film's ``style: {font: ...}`` names another
installed family (then its nearest weight). Colours left out are the film's text colour, or its
muted colour for headings, dividers and small print. Image files are taken from the
card file's folder and stay outside the repository (no logos in it).

:func:`load_card` reads a card file, :func:`card_image` draws it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.errors import Checker

KEYS = ("size", "background", "background_image", "blocks")
KINDS = ("image", "title", "divider", "names", "text")
WEIGHTS = ("regular", "light", "bold", "italic")
PLACE_KEYS = ("y", "gap")
BLOCK_KEYS = {
    "image": ("image", "height", "width"),
    "title": ("title", "size", "spacing", "weight", "colour"),
    "divider": ("divider", "thickness", "colour"),
    "names": ("names", "heading", "size", "spacing", "weight", "colour", "heading_size",
              "heading_gap", "heading_weight", "heading_colour"),
    "text": ("text", "size", "spacing", "weight", "colour"),
}
#: Defaults of each kind of block: the AFMS opening card's.
DEFAULTS = {
    "title": {"size": 60, "weight": "regular"},
    "divider": {"divider": 320, "thickness": 2},
    "names": {"size": 42, "spacing": 58, "weight": "light", "heading_size": 28,
              "heading_gap": 44, "heading_weight": "regular"},
    "text": {"size": 24, "weight": "regular"},
}
SPACING = 1.3              # lines' spacing, times their size, unless given
DEFAULT_SIZE = (1920, 1080)


@dataclass(frozen=True)
class Block:
    """One block of a card: ``kind`` (one of :data:`KINDS`), its ``keys`` checked
    (defaults filled in, colours ``None`` for the film's), and where it goes: ``y``
    pixels from the top, or ``gap`` pixels below the block before it."""

    kind: str
    keys: dict
    y: float | None = None
    gap: float = 0.0

    def __getitem__(self, name):
        return self.keys[name]

    def get(self, name, default=None):
        """The value of key ``name``, or ``default`` when it is not given."""
        return self.keys.get(name, default)


@dataclass
class Card:
    """A parsed card file: ``blocks`` top to bottom, the ``size`` its pixels are written
    for, its ``background`` colour and an optional ``background_image`` (scaled to cover
    the card). ``file`` is the card file."""

    blocks: list[Block]
    size: tuple[int, int] = DEFAULT_SIZE
    background: str = "black"
    background_image: Path | None = None
    file: str | None = None


def load_card(path: str | Path) -> Card:
    """Read the card file at ``path`` (includes resolved). Errors name the file."""
    from flowreel.yamlfile import read_yaml
    return card_from_dict(read_yaml(path), file=str(path))


def card_from_dict(data, file: str | None = None) -> Card:
    """Check ``data`` (a parsed YAML mapping) and build the :class:`Card`."""
    from flowreel.compose.style import colour
    check = Checker(file)
    data = check.mapping(data, KEYS, required=("blocks",))
    folder = Path(file).parent if file else Path(".")
    size = DEFAULT_SIZE
    if "size" in data:
        w, h = check.at("size").numbers(data["size"], 2)
        if w < 1 or h < 1 or w != int(w) or h != int(h):
            raise check.at("size").error(f"expected whole numbers of pixels, got [{w:g}, {h:g}]")
        size = (int(w), int(h))
    image = None
    if data.get("background_image") is not None:
        image = _file(data["background_image"], check.at("background_image"), folder)
    items = check.at("blocks").sequence(data["blocks"], minimum=1)
    blocks = [_block(spec, check.at("blocks", i), folder) for i, spec in enumerate(items)]
    return Card(blocks, size, colour(data.get("background", "black"), check.at("background")),
                image, file)


def _file(value, check: Checker, folder: Path) -> Path:
    path = folder / check.string(value)
    if not path.is_file():
        raise check.error(f"no image file {path}")
    return path


def _positive(value, check: Checker, zero: bool = False) -> float:
    n = check.number(value)
    if n < 0 or (n == 0 and not zero):
        raise check.error(f"must be {'at least 0' if zero else 'positive'}, got {n:g}")
    return n


def _lines(value, check: Checker) -> tuple[str, ...]:
    items = [value] if isinstance(value, str) else check.sequence(value, minimum=1)
    for i, t in enumerate(items):
        if not isinstance(t, str):
            raise check.at(i).error(f"expected a line of text, got {t!r} (quote a line "
                                    "holding ': ')")
    return tuple(items)


def _block(spec, check: Checker, folder: Path) -> Block:
    from flowreel.compose.style import colour
    if not isinstance(spec, dict):
        raise check.error(f"expected a block as a mapping, one of: {', '.join(KINDS)}")
    kinds = [k for k in KINDS if k in spec]
    if "heading" in spec and "names" not in spec:
        raise check.at("heading").error("is a heading of 'names'")
    if len(kinds) != 1:
        raise check.error(f"give one of {', '.join(KINDS)} in each block, got "
                          f"{', '.join(kinds) or 'none'}")
    kind = kinds[0]
    spec = check.mapping(spec, BLOCK_KEYS[kind] + PLACE_KEYS)
    if "y" in spec and "gap" in spec:
        raise check.at("gap").error("give 'y' or 'gap', not both")
    keys = dict(DEFAULTS.get(kind, {}))
    for name, value in spec.items():
        at = check.at(name)
        if name in PLACE_KEYS:
            continue
        if name == "image":
            keys[name] = _file(value, at, folder)
        elif name in ("title", "text", "names"):
            keys[name] = _lines(value, at)
        elif name == "heading":
            keys[name] = at.string(value)
        elif name in ("weight", "heading_weight"):
            keys[name] = at.choice(value, WEIGHTS)
        elif name in ("colour", "heading_colour"):
            keys[name] = colour(value, at)
        elif name == "divider":
            keys[name] = DEFAULTS["divider"]["divider"] if value is True else _positive(value, at)
        elif name == "heading_gap":
            keys[name] = _positive(value, at, zero=True)
        else:
            keys[name] = _positive(value, at)
    if kind == "image" and "height" in keys and "width" in keys:
        raise check.at("width").error("give 'height' or 'width', not both")
    if kind in ("title", "text") and "spacing" not in keys:
        keys["spacing"] = round(keys["size"] * SPACING)
    y = None if spec.get("y") is None else _positive(spec["y"], check.at("y"), zero=True)
    gap = check.at("gap").number(spec.get("gap", 0))
    return Block(kind, keys, y, gap)


def layout(card: Card) -> list[tuple[float, float]]:
    """Each block's ``(top, bottom)`` in pixels of the card, in order."""
    out, end = [], 0.0
    for b in card.blocks:
        top = b.y if b.y is not None else end + b.gap
        end = top + height(b)
        out.append((top, end))
    return out


def height(b: Block) -> float:
    """How tall block ``b`` is, in pixels: what the next block's ``gap`` starts from."""
    if b.kind == "image":
        if "height" in b.keys:
            return b["height"]
        from PIL import Image
        with Image.open(b["image"]) as im:
            return round(im.height * b["width"] / im.width) if "width" in b.keys else im.height
    if b.kind == "divider":
        return b["thickness"]
    if b.kind == "names":
        return (b["heading_gap"] if b.get("heading") else 0) + b["spacing"] * len(b["names"])
    return b["spacing"] * len(b[b.kind])


# Drawing ------------------------------------------------------------------------------

def font(weight: str, size: float, family: str = "Lato"):
    """A font of ``family`` and ``weight`` (``regular``, ``light``, ``bold`` or
    ``italic``) at ``size`` pixels, for Pillow. Lato is the bundled copy; another family
    is found among the machine's fonts through matplotlib, at the nearest weight (Times
    New Roman has no light weight, so its regular is used). A family that is not
    installed is an error naming it.

    Text is laid out by Pillow's basic engine on every machine: a Pillow built with
    raqm (conda-forge's) would otherwise kern it, and the same card would differ from
    one machine to another."""
    from PIL import ImageFont

    from flowreel.scene.text import font_file
    if family == "Lato":
        return ImageFont.truetype(font_file(weight.capitalize()), round(size),
                                  layout_engine=ImageFont.Layout.BASIC)
    from matplotlib import font_manager
    props = font_manager.FontProperties(
        family=family, style="italic" if weight == "italic" else "normal",
        weight={"italic": "normal", "regular": "normal"}.get(weight, weight))
    try:
        path = font_manager.findfont(props, fallback_to_default=False)
    except ValueError:
        raise ValueError(f"font {family!r} is not installed on this machine (style: font in "
                         "the film file)") from None
    return ImageFont.truetype(path, round(size), layout_engine=ImageFont.Layout.BASIC)


def _rgb(value: str) -> tuple[int, int, int]:
    from matplotlib.colors import to_rgb
    return tuple(round(c * 255) for c in to_rgb(value))


def _centred(draw, width: int, y: float, text: str, fnt, fill) -> None:
    """``text`` centred across a card ``width`` pixels wide, its top (ascender) at ``y``."""
    draw.text(((width - draw.textlength(text, font=fnt)) / 2, y), text, font=fnt, fill=fill)


def _background(card: Card):
    from PIL import Image
    image = Image.new("RGB", card.size, _rgb(card.background))
    if card.background_image is not None:
        back = Image.open(card.background_image).convert("RGB")
        k = max(card.size[0] / back.width, card.size[1] / back.height)
        back = back.resize((round(back.width * k), round(back.height * k)), Image.LANCZOS)
        left, top = (back.width - card.size[0]) // 2, (back.height - card.size[1]) // 2
        image.paste(back.crop((left, top, left + card.size[0], top + card.size[1])))
    return image


def card_image(card: Card, style=None, size: tuple[int, int] | None = None):
    """Draw ``card``: a Pillow RGB image ``size`` (width, height) pixels, the card's own
    size by default (another size scales the whole card). ``style`` is the film's
    :class:`~flowreel.film.schema.FilmStyle`, for its font and for colours a block
    leaves out."""
    from PIL import Image, ImageDraw

    from flowreel.film.schema import FilmStyle
    style = style or FilmStyle()
    text, muted = _rgb(style.text), _rgb(style.muted)
    image = _background(card)
    draw = ImageDraw.Draw(image)
    width = card.size[0]
    for b, (top, _) in zip(card.blocks, layout(card)):
        fill = _rgb(b["colour"]) if b.get("colour") else None
        if b.kind == "image":
            logo = Image.open(b["image"]).convert("RGBA")
            h = height(b)
            logo = logo.resize((round(logo.width * h / logo.height), round(h)), Image.LANCZOS)
            image.paste(logo, ((width - logo.width) // 2, round(top)), logo)
        elif b.kind == "divider":
            half = b["divider"] / 2
            draw.line((width / 2 - half, top, width / 2 + half, top), fill=fill or muted,
                      width=round(b["thickness"]))
        elif b.kind == "names":
            y = top
            if b.get("heading"):
                hf = _rgb(b["heading_colour"]) if b.get("heading_colour") else muted
                _centred(draw, width, y, b["heading"],
                         font(b["heading_weight"], b["heading_size"], style.font), hf)
                y += b["heading_gap"]
            fnt = font(b["weight"], b["size"], style.font)
            for i, name in enumerate(b["names"]):
                _centred(draw, width, y + i * b["spacing"], name, fnt, fill or text)
        else:
            fnt = font(b["weight"], b["size"], style.font)
            default = text if b.kind == "title" else muted
            for i, line in enumerate(b[b.kind]):
                _centred(draw, width, top + i * b["spacing"], line, fnt, fill or default)
    if size is not None and tuple(size) != card.size:
        image = image.resize(tuple(size), Image.LANCZOS)
    return image
