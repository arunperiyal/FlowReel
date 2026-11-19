"""The layout file (plan Section 9.1): tiles of frames placed in one picture.

.. code-block:: yaml

    size: [1920, 1080]
    background: black
    tiles:
      - {frames: frames/bare_panel, at: [0, 0], size: [1280, 540], label: bare}
      - {frames: frames/helical_panel, at: [0, 540], size: [1280, 540]}
      - {panel: panels/lift.yml, at: [1280, 0], size: [640, 1080]}

A ``panel`` tile names a panel file; :func:`flowreel.compose.layout` draws the panel
first and tiles its frames like any other folder of frames. ``rate: output`` marks a
panel the film draws at its output rate (plan Section 9.3).

or, placed automatically in rows and columns with a gap between them:

.. code-block:: yaml

    size: [1920, 1080]
    grid: [2, 2]
    gap: 8
    tiles: [{frames: frames/a}, {frames: frames/b}, {frames: frames/c}]

Positions and sizes are in pixels of the composed picture, ``at`` being a tile's upper
left corner, x to the right and y down (as image files count). Tile ``frames`` folders
are taken from the layout file's folder when relative. :func:`load` reads a file,
:func:`from_dict` a parsed mapping; both raise
:class:`~flowreel.scene.errors.ConfigError` naming the file and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from flowreel.scene.errors import Checker, ConfigError

KEYS = ("name", "size", "background", "grid", "gap", "missing", "tiles")
MISSING = ("error", "hold")
TILE_KEYS = ("frames", "stations", "panel", "rate", "at", "size", "along", "fit", "label")
RATES = ("flow", "output")
STATIONS_KEYS = ("shot", "at")
ALONG = ("row", "column")
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

    A tile of a ``stations`` entry has ``shot``, the shot rendered at ``station`` (a
    :class:`~flowreel.scene.shot.Shot` with its crop and camera moved there, see
    :func:`flowreel.compose.stations.at_station`), and ``frames`` ``None`` until
    :func:`flowreel.compose.layout` renders it. A ``panel`` tile has ``panel``, the
    panel file (resolved), and ``frames`` ``None`` until the layout draws it; ``rate``
    is ``flow`` (drawn at the layout's frames) or ``output`` (drawn at the film's
    output frames when the layout is given them). ``entry`` is the index in the file's
    ``tiles`` of the entry that made the tile, for error messages.
    """

    frames: Path | None
    at: tuple[int, int]
    size: tuple[int, int]
    fit: str = "contain"
    label: Label | None = None
    shot: object = None
    station: float | None = None
    entry: int | None = None
    panel: Path | None = None
    rate: str = "flow"


@dataclass
class Layout:
    """A parsed layout file: the picture's ``name``, ``size`` ``(width, height)`` in
    pixels, ``background`` colour and ``tiles``, drawn in order (later tiles on top).
    ``missing`` is what a tile without a frame at some index does: ``error`` or
    ``hold`` (show its nearest earlier frame, or its first one)."""

    name: str
    size: tuple[int, int]
    tiles: list[Tile]
    background: str = "black"
    missing: str = "error"
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
    missing = check.at("missing").choice(data.get("missing", "error"), MISSING)
    gap = check.at("gap").integer(data.get("gap", 0), minimum=0)
    grid = None if data.get("grid") is None else _pair(data["grid"], check.at("grid"), minimum=1)
    if grid is None and "gap" in data:
        raise check.at("gap").error("is used only with 'grid'")
    items = check.at("tiles").sequence(data["tiles"], minimum=1)
    counts = [_count(spec, check.at("tiles", i)) for i, spec in enumerate(items)]
    cells = None
    if grid is not None:
        if sum(counts) > grid[0] * grid[1]:
            raise check.at("tiles").error(f"{sum(counts)} tiles do not fit a grid of "
                                          f"{grid[0]} x {grid[1]}")
        try:
            cells = grid_cells(size, grid, gap)
        except ValueError as exc:
            raise check.at("gap").wrap(exc) from None
    tiles, where, first = [], [], 0
    for i, (spec, n) in enumerate(zip(items, counts)):
        mine = None if cells is None else cells[first:first + n]
        made = [replace(t, entry=i) for t in _tiles(spec, check.at("tiles", i), folder, mine, gap)]
        tiles += made
        where += [check.at("tiles", i)] * len(made)
        first += n
    for tile, at in zip(tiles, where):
        _inside(tile, size, at)
    return Layout(name=name, size=size, tiles=tiles, background=background, missing=missing,
                  file=file)


def grid_cells(size: tuple[int, int], grid: tuple[int, int], gap: int = 0) -> list:
    """The cells of a ``grid`` (rows, columns) over a picture of ``size`` with ``gap``
    pixels between cells, row by row, as ``(at, size)`` pairs. Cell edges are rounded
    to whole pixels, so cells differ by at most one pixel and the last ones end at the
    picture's edge."""
    rows, cols = grid
    xs, ys = _edges(size[0], cols, gap), _edges(size[1], rows, gap)
    if any(b - a < 1 for a, b in xs + ys):
        raise ValueError(f"a gap of {gap} leaves no room for {rows} x {cols} cells")
    return [((x0, y0), (x1 - x0, y1 - y0)) for (y0, y1) in ys for (x0, x1) in xs]


def _edges(length: int, n: int, gap: int) -> list[tuple[int, int]]:
    cell = (length - (n - 1) * gap) / n
    return [(round(i * (cell + gap)), round(i * (cell + gap) + cell)) for i in range(n)]


def _count(spec, check: Checker) -> int:
    """How many tiles an entry of ``tiles`` makes: one, or one per station."""
    if isinstance(spec, dict) and isinstance(spec.get("stations"), dict) \
            and isinstance(spec["stations"].get("at"), list):
        return max(1, len(spec["stations"]["at"]))
    return 1


def _tiles(spec, check: Checker, folder: Path, cells, gap: int) -> list[Tile]:
    """The tiles of one entry: ``{frames: ...}`` and ``{panel: ...}`` make one,
    ``{stations: ...}`` one per station, in the entry's grid cells or along its own
    ``at`` and ``size``."""
    spec = check.mapping(spec, TILE_KEYS)
    given = [k for k in ("frames", "stations", "panel") if k in spec]
    if len(given) != 1:
        raise check.error("give one of 'frames' (a folder of frames), 'stations' "
                          "(a shot and its stations) or 'panel' (a panel file)")
    if "rate" in spec and "panel" not in spec:
        raise check.at("rate").error("is used only with 'panel'")
    if cells is not None:
        for key in ("at", "size"):
            if key in spec:
                raise check.at(key).error("is set by 'grid'; leave it out, or drop the grid")
    else:
        for key in ("at", "size"):
            if key not in spec:
                raise check.error(f"missing key {key!r} (or place the tiles with 'grid')")
    fit = check.at("fit").choice(spec.get("fit", "contain"), FITS)
    if "panel" in spec:
        if "along" in spec:
            raise check.at("along").error("is used only with 'stations'")
        path = (folder / check.at("panel").string(spec["panel"])).resolve()
        if not path.is_file():
            raise check.at("panel").error(f"no panel file {path}")
        at, size = cells[0] if cells else (_pair(spec["at"], check.at("at"), minimum=0),
                                           _pair(spec["size"], check.at("size"), minimum=1))
        return [Tile(frames=None, at=at, size=size, fit=fit, panel=path,
                     rate=check.at("rate").choice(spec.get("rate", "flow"), RATES),
                     label=_label(spec.get("label"), check.at("label")))]
    if "frames" in spec:
        if "along" in spec:
            raise check.at("along").error("is used only with 'stations'")
        frames = folder / check.at("frames").string(spec["frames"])
        at, size = cells[0] if cells else (_pair(spec["at"], check.at("at"), minimum=0),
                                           _pair(spec["size"], check.at("size"), minimum=1))
        return [Tile(frames=frames, at=at, size=size, fit=fit,
                     label=_label(spec.get("label"), check.at("label")))]
    from flowreel.compose.stations import DEFAULT_LABEL, at_station, read_shot
    st = check.at("stations").mapping(spec["stations"], STATIONS_KEYS, required=STATIONS_KEYS)
    shot = read_shot(folder / check.at("stations", "shot").string(st["shot"]),
                     check.at("stations", "shot"))
    values = check.at("stations", "at").sequence(st["at"], minimum=1)
    stations = [check.at("stations", "at", k).number(v) for k, v in enumerate(values)]
    if cells is None:
        along = check.at("along").choice(spec.get("along", "row"), ALONG)
        area = _pair(spec["size"], check.at("size"), minimum=1)
        x0, y0 = _pair(spec["at"], check.at("at"), minimum=0)
        grid = (1, len(stations)) if along == "row" else (len(stations), 1)
        try:
            cells = [((x0 + x, y0 + y), wh) for (x, y), wh in grid_cells(area, grid, gap)]
        except ValueError as exc:
            raise check.at("size").wrap(exc) from None
    elif "along" in spec:
        raise check.at("along").error("is set by 'grid'; leave it out, or drop the grid")
    label = _label(spec.get("label", DEFAULT_LABEL), check.at("label"))
    out = []
    for k, (station, (at, size)) in enumerate(zip(stations, cells)):
        text = None
        if label is not None:
            try:
                text = label.text.format(station=station)
            except (KeyError, IndexError, ValueError) as exc:
                raise check.at("label").error(f"cannot format {label.text!r} with "
                                              f"{{station}}: {exc}") from None
        out.append(Tile(frames=None, at=at, size=size, fit=fit,
                        label=None if label is None else replace(label, text=text),
                        shot=at_station(shot, station, check.at("stations", "at", k)),
                        station=station))
    return out


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



def scaled(layout: Layout, size: tuple[int, int]) -> Layout:
    """``layout`` drawn at ``size`` (a draft): positions and tile sizes scaled by the
    ratios of the widths and of the heights, label sizes by that of the heights, all
    rounded to whole pixels."""
    sx, sy = size[0] / layout.size[0], size[1] / layout.size[1]
    if (sx, sy) == (1, 1):
        return layout
    tiles = []
    for t in layout.tiles:
        x0, y0 = round(t.at[0] * sx), round(t.at[1] * sy)
        x1, y1 = round((t.at[0] + t.size[0]) * sx), round((t.at[1] + t.size[1]) * sy)
        label = None if t.label is None else replace(t.label, size=t.label.size * sy)
        tiles.append(replace(t, at=(x0, y0), size=(max(1, x1 - x0), max(1, y1 - y0)),
                             label=label))
    return replace(layout, size=tuple(size), tiles=tiles)
