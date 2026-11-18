"""The layout file (plan Section 9.1): tiles of frames placed in one picture.

.. code-block:: yaml

    size: [1920, 1080]
    background: black
    tiles:
      - {frames: frames/bare_panel, at: [0, 0], size: [1280, 540], label: bare}
      - {frames: frames/helical_panel, at: [0, 540], size: [1280, 540]}

Positions and sizes are in pixels of the composed picture, ``at`` being a tile's upper
left corner, x to the right and y down (as image files count). Tile ``frames`` folders
are taken from the layout file's folder when relative. :func:`load` reads a file,
:func:`from_dict` a parsed mapping; both raise
:class:`~flowreel.scene.errors.ConfigError` naming the file and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from flowreel.scene.errors import Checker, ConfigError

KEYS = ("name", "size", "background", "tiles")
TILE_KEYS = ("frames", "at", "size", "fit", "label")
LABEL_KEYS = ("text", "corner", "size", "colour")
FITS = ("contain", "cover", "stretch")
CORNERS = ("upper_left", "upper_right", "lower_left", "lower_right")
DEFAULT_SIZE = (1920, 1080)


@dataclass(frozen=True)
class Label:
    """Text written over a tile: ``text`` in ``corner``, ``size`` pixels high, in
    ``colour`` (a colour name or ``#rrggbb``), in the bundled Lato."""

    text: str
    corner: str = "upper_left"
    size: float = 28.0
    colour: str = "#ffffff"


@dataclass(frozen=True)
class Tile:
    """One tile of a layout.

    ``frames`` is the folder of its frames (resolved). ``at`` is the upper left corner
    and ``size`` the ``(width, height)`` in the composed picture, in pixels. ``fit``
    says how a frame of another shape fills the tile: ``contain`` (whole frame, centred,
    bars of the background), ``cover`` (fills the tile, edges cut) or ``stretch``.
    ``label`` is a :class:`Label` or ``None``.
    """

    frames: Path
    at: tuple[int, int]
    size: tuple[int, int]
    fit: str = "contain"
    label: Label | None = None


@dataclass
class Layout:
    """A parsed layout file: the picture's ``name``, ``size`` ``(width, height)`` in
    pixels, ``background`` colour and ``tiles``, drawn in order (later tiles on top)."""

    name: str
    size: tuple[int, int]
    tiles: list[Tile]
    background: str = "black"
    file: str | None = None


def load(path: str | Path) -> Layout:
    """Read the layout file at ``path``. Errors name the file."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark else "syntax"
        raise ConfigError(f"{where}: {getattr(exc, 'problem', None) or exc}", path) from None
    return from_dict(data, file=str(path))


def from_dict(data, file: str | None = None) -> Layout:
    """Check ``data`` (a parsed YAML mapping) and build the :class:`Layout`.

    ``name`` defaults to the file's stem (``layout`` without a file)."""
    check = Checker(file)
    data = check.mapping(data, KEYS, required=("tiles",))
    name = check.at("name").string(data.get("name", Path(file).stem if file else "layout"))
    size = _pair(data.get("size", DEFAULT_SIZE), check.at("size"), minimum=1)
    background = _colour(data.get("background", "black"), check.at("background"))
    folder = Path(file).parent if file else Path(".")
    items = check.at("tiles").sequence(data["tiles"], minimum=1)
    tiles = [_tile(spec, check.at("tiles", i), folder) for i, spec in enumerate(items)]
    for i, tile in enumerate(tiles):
        _inside(tile, size, check.at("tiles", i))
    return Layout(name=name, size=size, tiles=tiles, background=background, file=file)


def _tile(spec, check: Checker, folder: Path) -> Tile:
    spec = check.mapping(spec, TILE_KEYS, required=("frames", "at", "size"))
    frames = folder / check.at("frames").string(spec["frames"])
    at = _pair(spec["at"], check.at("at"), minimum=0)
    size = _pair(spec["size"], check.at("size"), minimum=1)
    fit = check.at("fit").choice(spec.get("fit", "contain"), FITS)
    label = _label(spec.get("label"), check.at("label"))
    return Tile(frames=frames, at=at, size=size, fit=fit, label=label)


def _label(value, check: Checker) -> Label | None:
    """``label: TEXT`` or ``label: {text, corner, size, colour}``."""
    if value is None:
        return None
    if isinstance(value, str):
        return Label(check.string(value))
    spec = check.mapping(value, LABEL_KEYS, required=("text",))
    size = check.at("size").number(spec.get("size", Label.size))
    if size <= 0:
        raise check.at("size").error(f"must be positive, got {size:g}")
    return Label(text=check.at("text").string(spec["text"]),
                 corner=check.at("corner").choice(spec.get("corner", Label.corner), CORNERS),
                 size=size, colour=_colour(spec.get("colour", Label.colour), check.at("colour")))


def _pair(value, check: Checker, minimum: int) -> tuple[int, int]:
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected two whole numbers, got {len(items)} entries")
    return tuple(check.at(i).integer(v, minimum=minimum) for i, v in enumerate(items))


def _colour(value, check: Checker) -> str:
    """A colour name PIL knows (``black``) or ``#rgb``/``#rrggbb``."""
    from PIL import ImageColor
    text = check.string(value)
    try:
        ImageColor.getrgb(text)
    except ValueError:
        raise check.error(f"expected a colour name or '#rrggbb', got {text!r}") from None
    return text


def _inside(tile: Tile, size: tuple[int, int], check: Checker) -> None:
    (x, y), (w, h) = tile.at, tile.size
    if x + w > size[0] or y + h > size[1]:
        raise check.error(f"the tile ({w} x {h} at [{x}, {y}]) runs past the picture's "
                          f"{size[0]} x {size[1]}")

