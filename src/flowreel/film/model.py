"""A film of scenes (plan Section 19.11, Phase 10): ``film.yml`` described in levels.

.. code-block:: yaml

    output: film.mp4
    fps: 24
    size: [1920, 1080]
    style: {font: Lato, looks: {title: {size: 64}}}
    audio: [{file: assets/music.mp3, fade: [1.5, 4]}]
    watermark: {text: 'A. Author', corner: lower_right}
    scenes:
      - name: opening                       # a title card: a scene of text and images
        seconds: 6
        fade: [1.5, 1.5]
        chapter: Opening
        layout:
          boxes:
            - {image: assets/logo.png, pos: [810, 100], size: [300, 190]}
            - {text: {lines: ['Helical grooves'], look: title}, place: centre}
      - name: reveal                        # a shot: a scene of one box
        layout: {boxes: [{shot: shots/reveal.yml}]}
      - name: compare
        layout: compare                     # layouts/compare.yml
        cross: 1.0
      - name: end
        seconds: 8
        layout: {boxes: [{last_frame: compare}]}

**Levels.** The film's properties (``output``, ``fps``, ``size``, ``style``), its
``audio`` and ``watermark``, and its ``scenes`` in order. A scene has a ``layout``,
written in place or in ``layouts/NAME.yml`` and named by ``NAME`` (or by a path ending in
``.yml``, from the film file's folder). A layout has an optional ``background`` and its
``boxes``, drawn in order, the first at the back.

**A box** is one element. Its own keys are where and when it shows: ``name``; ``pos:
[x, y]`` (upper left corner) and ``size: [w, h]`` in the film's pixels, or ``place``
(:data:`PLACES`), or neither (the whole frame); ``at: [start, end]`` in seconds into the
scene (``end`` left out or ``~``: to its end) and ``fade`` (seconds, or ``[in, out]``);
for text and shapes, ``follow: {box, model, offset}`` instead of a place, pinning the
box to a point of the flow shown by a shot box. What it shows is under one key, written
short or as a mapping of options:

=============  ====================================  ====================================
kind           short                                 options
=============  ====================================  ====================================
``text``       a line, or a list of lines            :data:`TEXT_KEYS`
``image``      a picture file                        ``file``, ``fit``, ``opacity``
``shape``      a kind of shape (:data:`SHAPES`)      :data:`SHAPE_KEYS`
``shot``       a shot file                           ``file`` or ``frames``, ``rate``,
                                                     ``freezes``
``panel``      a panel file                          ``file``
``last_frame`` a scene's name                        (none)
=============  ====================================  ====================================

**Length.** A scene lasts as long as its main box's frames, freezes included: the box
named ``main``, else its first ``shot`` or ``panel`` box. A scene without one (text,
pictures, a held last frame) gives ``seconds``; a scene with one may not.

**Between scenes:** ``fade: [in, out]`` from and to black, ``cross: SECONDS`` dissolving
into the next scene. A scene's ``chapter`` starts a chapter.

:func:`load` reads a file, :func:`from_dict` a parsed mapping; both raise
:class:`~flowreel.scene.errors.ConfigError` naming the file (the layout file, for a
box written there) and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.film.schema import (ALIGN, AUDIO_KEYS, CORNERS, DEFAULT_SIZE, MATHS,
                                  WATERMARK_KEYS, Audio, Chapter, Rate, Watermark, _audio,
                                  _bool, _chapter, _colour, _fade, _pair, _positive, _rate,
                                  parse_watermark)
from flowreel.scene.errors import Checker

KEYS = ("output", "fps", "size", "style", "audio", "watermark", "scenes")
SCENE_KEYS = ("name", "layout", "seconds", "fade", "cross", "chapter")
LAYOUT_KEYS = ("background", "boxes")
KINDS = ("text", "image", "shape", "shot", "panel", "last_frame")
BOX_KEYS = ("name", "pos", "size", "place", "at", "fade", "follow") + KINDS
#: Where ``place`` puts a box: the whole frame, a half, the middle, or a quarter.
PLACES = ("full", "top", "bottom", "left", "right", "centre",
          "top_left", "top_right", "bottom_left", "bottom_right")
FOLLOW_KEYS = ("box", "model", "offset")
STYLE_KEYS = ("font", "maths", "colours", "looks")
COLOUR_KEYS = ("text", "muted")
WEIGHTS = ("regular", "light", "bold", "italic")
VALIGN = ("top", "centre", "bottom")
#: A look: how text is drawn unless the box says otherwise.
LOOK_KEYS = ("size", "colour", "weight", "align", "valign", "spacing", "shadow", "box",
             "fade", "margin")
LOOKS = ("title", "text", "small")
TEXT_KEYS = ("lines", "look", "subtitle") + LOOK_KEYS
IMAGE_KEYS = ("file", "fit", "opacity")
FITS = ("contain", "cover", "stretch")
SHAPES = ("line", "arrow", "rectangle", "circle")
SHAPE_KEYS = ("kind", "colour", "width", "fill", "head", "direction", "radius", "shadow")
#: Which way a line or arrow crosses its box, from the middle of one side (or a corner)
#: to the opposite one.
DIRECTIONS = ("right", "left", "up", "down", "up_right", "up_left", "down_right", "down_left")
SHOT_KEYS = ("file", "frames", "rate", "freezes")
FREEZE_KEYS = ("at", "hold")
PANEL_KEYS = ("file", "rate", "freezes")
SCENE_WATERMARK_KEYS = tuple(k for k in WATERMARK_KEYS if k not in ("shots", "cards")) + ("scenes",)


@dataclass(frozen=True)
class Look:
    """How text looks: letter ``size`` in pixels, ``colour`` (``None``: the film's text
    colour), ``weight`` (:data:`WEIGHTS`), ``align`` of the lines and ``valign`` in the
    box, line ``spacing`` (times the size), a soft ``shadow`` or a dark ``box`` behind,
    ``fade`` in and out (seconds) and ``margin`` from the box's edges (pixels)."""

    size: float = 50.0
    colour: str | None = None
    weight: str = "regular"
    align: str = "centre"
    valign: str = "centre"
    spacing: float = 1.3
    shadow: bool = True
    box: bool = False
    fade: float = 0.8
    margin: float = 40.0


#: The looks a film starts from; ``style: {looks: ...}`` changes them.
DEFAULT_LOOKS = {
    "title": Look(size=64.0, shadow=False, fade=0.0),
    "text": Look(),
    "small": Look(size=26.0, colour="muted", shadow=False, fade=0.0),
}


@dataclass(frozen=True)
class Style:
    """The film's text: ``font`` family (Lato is bundled), ``maths`` (the font of text
    between ``$``), the ``text`` and ``muted`` colours, and its ``looks`` by name."""

    font: str = "Lato"
    maths: str = "font"
    text: str = "#f2f2f2"
    muted: str = "#96a5b2"
    looks: dict = field(default_factory=lambda: dict(DEFAULT_LOOKS))


@dataclass(frozen=True)
class Text:
    """A text box's content: ``lines`` (``$...$`` is mathematics), the ``look`` it starts
    from and the ``Look`` it ends with (``drawn``, the look with the box's own keys), and
    ``subtitle``: whether it goes into ``film.srt`` when timed."""

    lines: tuple[str, ...]
    look: str
    drawn: Look
    subtitle: bool = True


@dataclass(frozen=True)
class Image:
    """An image box's content: the picture ``file``, how it ``fit``\\ s the box
    (:data:`FITS`) and its ``opacity``."""

    file: Path
    fit: str = "contain"
    opacity: float = 1.0


@dataclass(frozen=True)
class Shape:
    """A shape box's content: a ``kind`` (:data:`SHAPES`) drawn in its box: a rectangle
    its outline (``radius`` rounds the corners), a circle the ellipse within it, a line or
    arrow across it in ``direction``. ``colour`` (``None``: the film's text colour), line
    ``width`` and arrow ``head`` in pixels, ``fill`` (a colour, or ``None``), and a soft
    ``shadow`` as text has."""

    kind: str
    colour: str | None = None
    width: float = 4.0
    fill: str | None = None
    head: float = 18.0
    direction: str = "right"
    radius: float = 0.0
    shadow: bool = False


@dataclass(frozen=True)
class Freeze:
    """Stop a shot box at ``at`` seconds of its own frames for ``hold`` seconds."""

    at: float
    hold: float


@dataclass(frozen=True)
class ShotBox:
    """A shot box's content: the shot ``file`` (its frames are ``frames/<its name>``
    under the project), or a ``frames`` folder drawn elsewhere; its ``rate`` and
    ``freezes``."""

    file: Path | None
    frames: Path | None
    rate: Rate
    freezes: tuple[Freeze, ...] = ()


@dataclass(frozen=True)
class PanelBox:
    """A panel box's content: the panel ``file``, drawn by the build at the box's size
    on every output frame, at the time between its frames there; its ``rate`` (its
    frames a second: ``to_output`` does not apply, a panel is never interpolated) and
    ``freezes``."""

    file: Path
    rate: Rate
    freezes: tuple[Freeze, ...] = ()


@dataclass(frozen=True)
class LastFrame:
    """A box holding the last frame of the scene called ``scene``."""

    scene: str


@dataclass(frozen=True)
class Follow:
    """A box pinned to ``model`` (a point ``[x, y, z]`` in the flow's units) as the
    camera of shot box ``box`` shows it, moved by ``offset`` pixels on the screen."""

    box: str
    model: tuple[float, float, float]
    offset: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class Box:
    """One element of a layout: its ``name``, ``kind`` (:data:`KINDS`) and ``content``,
    where it is (``pos`` and ``size`` in pixels, ``None`` when not given; ``place``; or
    ``follow``), and when: ``at`` (start, end) in seconds into the scene (end ``None``:
    to its end; ``at`` ``None``: the whole scene) and ``fade`` (in, out) (``None``: the
    kind's default, a text's look)."""

    name: str
    kind: str
    content: object
    pos: tuple[float, float] | None = None
    size: tuple[float, float] | None = None
    place: str | None = None
    at: tuple[float, float | None] | None = None
    fade: tuple[float, float] | None = None
    follow: Follow | None = None

    def rect(self, frame: tuple[int, int]) -> tuple[float, float, float, float] | None:
        """``(x, y, w, h)`` in pixels of a ``frame`` ``(width, height)``; ``None`` when the
        box has no size of its own (a text at ``pos``, sized by its text, or following)."""
        W, H = frame
        if self.pos is not None and self.size is not None:
            return (*self.pos, *self.size)
        if self.pos is not None or self.follow is not None:
            return None
        return place_rect(self.place or "full", frame)


def place_rect(place: str, frame: tuple[int, int]) -> tuple[float, float, float, float]:
    """The rectangle ``(x, y, w, h)`` of ``place`` (:data:`PLACES`) in ``frame``."""
    W, H = frame
    return {
        "full": (0, 0, W, H), "top": (0, 0, W, H / 2), "bottom": (0, H / 2, W, H / 2),
        "left": (0, 0, W / 2, H), "right": (W / 2, 0, W / 2, H),
        "centre": (W / 4, H / 4, W / 2, H / 2),
        "top_left": (0, 0, W / 2, H / 2), "top_right": (W / 2, 0, W / 2, H / 2),
        "bottom_left": (0, H / 2, W / 2, H / 2), "bottom_right": (W / 2, H / 2, W / 2, H / 2),
    }[place]


@dataclass(frozen=True)
class Layout:
    """A scene's layout: its ``boxes`` in drawing order (first at the back), its
    ``background`` colour, and the ``file`` it was read from (``None``: in place)."""

    boxes: tuple[Box, ...]
    background: str = "#000000"
    file: Path | None = None

    def box(self, name: str) -> Box:
        """The box called ``name``; ``KeyError`` naming the boxes otherwise."""
        for b in self.boxes:
            if b.name == name:
                return b
        raise KeyError(f"no box {name!r} (boxes: {', '.join(b.name for b in self.boxes)})")

    @property
    def main(self) -> Box | None:
        """The box whose frames set the scene's length: the one named ``main``, else the
        first shot or panel box; ``None`` when there is none."""
        named = [b for b in self.boxes if b.name == "main"]
        if named:
            return named[0]
        return next((b for b in self.boxes if b.kind in ("shot", "panel")), None)


@dataclass(frozen=True)
class Scene:
    """One scene: its ``name``, ``layout``, ``seconds`` (``None``: its main box's
    length), ``fade`` (in, out) from and to black, ``cross`` (seconds dissolving into the
    next scene) and ``chapter`` (or ``None``)."""

    name: str
    layout: Layout
    seconds: float | None = None
    fade: tuple[float, float] = (0.0, 0.0)
    cross: float = 0.0
    chapter: Chapter | None = None


@dataclass
class Film:
    """A film of scenes: ``output``, ``fps``, ``size`` (width, height), ``style``,
    ``audio`` tracks, ``watermark`` (its ``shots`` are scene names) and ``scenes`` in
    order. ``file`` is the film file; relative paths in it start at its folder."""

    output: Path
    fps: int
    size: tuple[int, int]
    scenes: list[Scene]
    style: Style = field(default_factory=Style)
    audio: tuple[Audio, ...] = ()
    watermark: Watermark | None = None
    file: str | None = None

    @property
    def folder(self) -> Path:
        """Where relative paths in the film file start."""
        return Path(self.file).parent if self.file else Path(".")

    def scene(self, name: str) -> Scene:
        """The scene called ``name``; ``KeyError`` naming the scenes otherwise."""
        for s in self.scenes:
            if s.name == name:
                return s
        raise KeyError(f"no scene {name!r} (scenes: {', '.join(s.name for s in self.scenes)})")


def is_scene_film(data) -> bool:
    """Whether a parsed film file is a film of scenes (it has ``scenes:``)."""
    return isinstance(data, dict) and "scenes" in data


def load(path: str | Path) -> Film:
    """Read the film file at ``path``. Errors name the file."""
    from flowreel.yamlfile import read_yaml
    return from_dict(read_yaml(path), file=str(path))


def from_dict(data, file: str | None = None) -> Film:
    """Check ``data`` (a parsed YAML mapping) and build the :class:`Film`."""
    check = Checker(file)
    if isinstance(data, dict) and "shots" in data and "scenes" not in data:
        raise check.error("a film of shots is not read any more: write 'scenes:', each a "
                          "layout of boxes (flowreel film template; "
                          "docs/guide/film/film.md)")
    data = check.mapping(data, KEYS, required=("scenes",))
    folder = Path(file).parent if file else Path(".")
    fps = check.at("fps").integer(data.get("fps", 24), minimum=1)
    size = _pair(data.get("size", DEFAULT_SIZE), check.at("size"))
    style = _style(data.get("style"), check.at("style"))
    audio = _audio(data.get("audio"), check.at("audio"), folder)
    items = check.at("scenes").sequence(data["scenes"], minimum=1)
    scenes = [_scene(spec, check.at("scenes", i), folder, fps, size, style.looks)
              for i, spec in enumerate(items)]
    names = [s.name for s in scenes]
    for i, s in enumerate(scenes):
        if names.index(s.name) != i:
            raise check.at("scenes", i, "name").error(f"scene {s.name!r} is named twice")
    for i, s in enumerate(scenes):
        _check_scene(s, check.at("scenes", i), names, i == len(scenes) - 1)
    watermark = None
    if data.get("watermark") is not None:
        watermark = _watermark(data["watermark"], check.at("watermark"), folder, names)
    output = folder / check.at("output").string(data.get("output", "film.mp4"))
    return Film(output, fps, size, scenes, style, audio, watermark, file)


def _style(value, check: Checker) -> Style:
    spec = check.mapping(value or {}, STYLE_KEYS)
    base = Style()
    colours = check.at("colours").mapping(spec.get("colours") or {}, COLOUR_KEYS)
    given = check.at("looks").mapping(spec.get("looks") or {}, LOOKS)
    looks = {name: _look(given.get(name), check.at("looks", name), DEFAULT_LOOKS[name])
             for name in LOOKS}
    return Style(font=check.at("font").string(spec.get("font", base.font)),
                 maths=check.at("maths").choice(spec.get("maths", base.maths), MATHS),
                 text=_colour(colours.get("text", base.text), check.at("colours", "text")),
                 muted=_colour(colours.get("muted", base.muted), check.at("colours", "muted")),
                 looks=looks)


def _look(spec, check: Checker, base: Look, keys=LOOK_KEYS) -> Look:
    """``base`` with the look keys of ``spec`` (a mapping, already checked or not)."""
    spec = {k: v for k, v in (spec or {}).items() if k in LOOK_KEYS}
    if not spec:
        return base
    out = dict(base.__dict__)
    for key, value in spec.items():
        at = check.at(key)
        if key in ("size", "spacing"):
            out[key] = _positive(value, at, zero=False)
        elif key in ("fade", "margin"):
            out[key] = _positive(value, at)
        elif key in ("shadow", "box"):
            out[key] = _bool(value, at)
        elif key == "weight":
            out[key] = at.choice(value, WEIGHTS)
        elif key == "align":
            out[key] = at.choice(value, ALIGN)
        elif key == "valign":
            out[key] = at.choice(value, VALIGN)
        elif key == "colour":
            out[key] = None if value is None else "muted" if value == "muted" \
                else _colour(value, at)
    return Look(**out)


def _watermark(value, check: Checker, folder: Path, names: list[str]) -> Watermark:
    spec = check.mapping(value, SCENE_WATERMARK_KEYS)
    scenes = spec.pop("scenes", None)
    w = parse_watermark(spec, check, folder)
    if scenes is not None:
        if w.seconds is not None:
            raise check.at("scenes").error("give 'scenes' or 'seconds', not both")
        items = check.at("scenes").sequence(scenes, minimum=1)
        chosen = tuple(check.at("scenes", k).string(s) for k, s in enumerate(items))
        for k, name in enumerate(chosen):
            if name not in names:
                raise check.at("scenes", k).error(f"no scene {name!r} (scenes: {', '.join(names)})")
        from dataclasses import replace
        w = replace(w, shots=chosen, cards=True)
    return w


def _scene(spec, check: Checker, folder: Path, fps: int, size, looks=None) -> Scene:
    spec = check.mapping(spec, SCENE_KEYS, required=("name", "layout"))
    name = check.at("name").string(spec["name"])
    layout = _layout_of(spec["layout"], check.at("layout"), folder, fps, size, looks)
    seconds = None if spec.get("seconds") is None else \
        _positive(spec["seconds"], check.at("seconds"), zero=False)
    return Scene(name, layout, seconds, _fade(spec.get("fade", [0, 0]), check.at("fade")),
                 _positive(spec.get("cross", 0.0), check.at("cross")),
                 _chapter(spec.get("chapter"), check.at("chapter")))


def layout_path(name: str, folder: Path) -> Path:
    """The file of a layout named in a film: ``layouts/NAME.yml`` beside the film file,
    or a path ending in ``.yml`` from its folder."""
    if name.endswith((".yml", ".yaml")):
        return folder / name
    return folder / "layouts" / f"{name}.yml"


def _layout_of(value, check: Checker, folder: Path, fps: int, size, looks=None) -> Layout:
    if isinstance(value, str):
        from flowreel.yamlfile import read_yaml
        path = layout_path(check.string(value), folder)
        if not path.is_file():
            raise check.error(f"no layout file {path}")
        return parse_layout(read_yaml(path), Checker(path), path.parent, fps, size, path, looks)
    return parse_layout(value, check, folder, fps, size, looks=looks)


def load_layout(path: str | Path, fps: int = 24, size=DEFAULT_SIZE, looks=None) -> Layout:
    """Read a layout file (``layouts/NAME.yml``) on its own: for a film of ``fps`` frames
    a second, ``size`` pixels."""
    from flowreel.yamlfile import read_yaml
    path = Path(path)
    return parse_layout(read_yaml(path), Checker(path), path.parent, fps, tuple(size), path,
                        looks)


def parse_layout(value, check: Checker, folder: Path, fps: int, size, file=None,
                 looks=None) -> Layout:
    """A layout's mapping (``background``, ``boxes``); paths from ``folder``. ``looks``
    are the film's (its ``style.looks``), which a text box starts from."""
    spec = check.mapping(value, LAYOUT_KEYS, required=("boxes",))
    items = check.at("boxes").sequence(spec["boxes"], minimum=1)
    boxes = [_box(item, check.at("boxes", i), folder, fps, size, i, looks)
             for i, item in enumerate(items)]
    names = [b.name for b in boxes]
    for i, b in enumerate(boxes):
        if names.index(b.name) != i:
            raise check.at("boxes", i, "name").error(f"box {b.name!r} is named twice")
        if b.follow is not None:
            at = check.at("boxes", i, "follow", "box")
            if b.follow.box not in names:
                raise at.error(f"no box {b.follow.box!r} (boxes: {', '.join(names)})")
            if boxes[names.index(b.follow.box)].kind != "shot":
                raise at.error(f"box {b.follow.box!r} is not a shot box: only a shot has a "
                               "camera to follow a point with")
    background = _colour(spec.get("background", "black"), check.at("background"))
    return Layout(tuple(boxes), background, None if file is None else Path(file))


def _pos(value, check: Checker, what: str) -> tuple[float, float]:
    a, b = check.numbers(value, 2)
    if what == "size" and (a <= 0 or b <= 0):
        raise check.error(f"a size is positive, got [{a:g}, {b:g}]")
    return (float(a), float(b))


def _box(spec, check: Checker, folder: Path, fps: int, size, index: int, looks=None) -> Box:
    spec = check.mapping(spec, BOX_KEYS)
    given = [k for k in KINDS if k in spec]
    if len(given) != 1:
        raise check.error("give one of " + ", ".join(f"'{k}'" for k in KINDS)
                          + (f" (got {', '.join(given)})" if given else ""))
    kind = given[0]
    name = check.at("name").string(spec["name"]) if spec.get("name") is not None \
        else f"{kind}{index + 1}"
    content = (_text(spec[kind], check.at(kind), folder, fps, looks) if kind == "text"
               else CONTENT[kind](spec[kind], check.at(kind), folder, fps))
    pos = None if spec.get("pos") is None else _pos(spec["pos"], check.at("pos"), "pos")
    bsize = None if spec.get("size") is None else _pos(spec["size"], check.at("size"), "size")
    place = None if spec.get("place") is None else check.at("place").choice(spec["place"], PLACES)
    follow = None if spec.get("follow") is None else _follow(spec["follow"], check.at("follow"))
    if follow is not None and kind not in ("text", "shape"):
        raise check.at("follow").error("only text and shape boxes follow a point")
    if place is not None and (pos is not None or bsize is not None or follow is not None):
        raise check.at("place").error("give 'place', or 'pos' and 'size', or 'follow'; not two")
    if follow is not None and pos is not None:
        raise check.at("follow").error("give 'follow' or 'pos', not both")
    if bsize is not None and pos is None and follow is None:
        raise check.at("size").error("a size needs 'pos' (its upper left corner) or 'follow'")
    if pos is not None and bsize is None and kind != "text":
        raise check.at("pos").error(f"a {kind} box at 'pos' needs its 'size' too (only a "
                                    "text box is sized by what it holds)")
    if follow is not None and kind == "shape" and bsize is None:
        raise check.at("size").error("a shape that follows a point needs its 'size'")
    at = None if spec.get("at") is None else _at(spec["at"], check.at("at"))
    fade = None if spec.get("fade") is None else _fade(spec["fade"], check.at("fade"))
    return Box(name, kind, content, pos, bsize, place, at, fade, follow)


def _at(value, check: Checker) -> tuple[float, float | None]:
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected [start, end] (end may be ~, to the scene's end), got "
                          f"{len(items)} entries")
    start = _positive(items[0], check.at(0))
    end = None if items[1] is None else _positive(items[1], check.at(1))
    if end is not None and end <= start:
        raise check.error(f"the end must come after the start, got [{start:g}, {end:g}]")
    return (start, end)


def _follow(value, check: Checker) -> Follow:
    spec = check.mapping(value, FOLLOW_KEYS, required=("box", "model"))
    model = tuple(float(v) for v in check.at("model").numbers(spec["model"], 3))
    offset = (0.0, 0.0) if spec.get("offset") is None else \
        tuple(float(v) for v in check.at("offset").numbers(spec["offset"], 2))
    return Follow(check.at("box").string(spec["box"]), model, offset)


def _options(value, check: Checker, short: str, keys) -> dict:
    """The options of a box's content: ``{short: value}`` for the short form."""
    if isinstance(value, dict):
        return check.mapping(value, keys)
    return {short: value}


def _text(value, check: Checker, folder: Path, fps: int, looks=None) -> Text:
    spec = _options(value, check, "lines", TEXT_KEYS)
    if spec.get("lines") is None:
        raise check.error("missing key 'lines' (a line of text, or a list of lines)")
    raw = spec["lines"]
    lines = [raw] if isinstance(raw, str) else check.at("lines").sequence(raw, minimum=1)
    lines = tuple(check.at("lines", i).string(line) if not isinstance(raw, str) else line
                  for i, line in enumerate(lines))
    look = check.at("look").choice(spec.get("look", "text"), LOOKS)
    drawn = _look(spec, check, (looks or DEFAULT_LOOKS)[look])
    return Text(lines, look, drawn, _bool(spec.get("subtitle", True), check.at("subtitle")))


def _image(value, check: Checker, folder: Path, fps: int) -> Image:
    spec = _options(value, check, "file", IMAGE_KEYS)
    if spec.get("file") is None:
        raise check.error("missing key 'file' (the picture)")
    path = folder / check.at("file").string(spec["file"])
    if not path.is_file():
        raise (check.at("file") if isinstance(value, dict) else check).error(
            f"no image file {path}")
    opacity = check.at("opacity").number(spec.get("opacity", 1.0))
    if not 0 <= opacity <= 1:
        raise check.at("opacity").error(f"expected 0 to 1, got {opacity:g}")
    return Image(path, check.at("fit").choice(spec.get("fit", "contain"), FITS), opacity)


def _shape(value, check: Checker, folder: Path, fps: int) -> Shape:
    spec = _options(value, check, "kind", SHAPE_KEYS)
    if spec.get("kind") is None:
        raise check.error(f"missing key 'kind' (one of {', '.join(SHAPES)})")
    kind = check.at("kind").choice(spec["kind"], SHAPES)
    if "direction" in spec and kind not in ("line", "arrow"):
        raise check.at("direction").error(f"is for a line or an arrow, not a {kind}")
    if "head" in spec and kind != "arrow":
        raise check.at("head").error(f"is for an arrow, not a {kind}")
    if "fill" in spec and kind not in ("rectangle", "circle"):
        raise check.at("fill").error(f"is for a rectangle or a circle, not a {kind}")
    if "radius" in spec and kind != "rectangle":
        raise check.at("radius").error(f"rounds a rectangle's corners, not a {kind}'s")
    colour = None if spec.get("colour") is None else _colour(spec["colour"], check.at("colour"))
    fill = None if spec.get("fill") is None else _colour(spec["fill"], check.at("fill"))
    return Shape(kind, colour, _positive(spec.get("width", 4.0), check.at("width"), zero=False),
                 fill, _positive(spec.get("head", 18.0), check.at("head"), zero=False),
                 check.at("direction").choice(spec.get("direction", "right"), DIRECTIONS),
                 _positive(spec.get("radius", 0.0), check.at("radius")),
                 _bool(spec.get("shadow", False), check.at("shadow")))


def _shot(value, check: Checker, folder: Path, fps: int) -> ShotBox:
    spec = _options(value, check, "file", SHOT_KEYS)
    given = [k for k in ("file", "frames") if spec.get(k) is not None]
    if len(given) != 1:
        raise check.error("give 'file' (a shot file) or 'frames' (a folder of frames drawn "
                          "elsewhere)")
    path = folder / check.at(given[0]).string(spec[given[0]])
    where = check.at(given[0]) if isinstance(value, dict) else check
    if given[0] == "file" and not path.is_file():
        raise where.error(f"no shot file {path}")
    return ShotBox(path if given[0] == "file" else None,
                   path if given[0] == "frames" else None,
                   _rate(spec.get("rate"), check.at("rate"), fps),
                   _freezes(spec.get("freezes"), check.at("freezes")))


def _freezes(value, check: Checker) -> tuple[Freeze, ...]:
    items = check.sequence(value or [])
    freezes = []
    for i, f in enumerate(items):
        at = check.at(i)
        f = at.mapping(f, FREEZE_KEYS, required=("at", "hold"))
        freezes.append(Freeze(_positive(f["at"], at.at("at")),
                              _positive(f["hold"], at.at("hold"), zero=False)))
    if [f.at for f in freezes] != sorted(f.at for f in freezes):
        raise check.error("freezes must be in order of 'at'")
    return tuple(freezes)


def _panel(value, check: Checker, folder: Path, fps: int) -> PanelBox:
    spec = _options(value, check, "file", PANEL_KEYS)
    if spec.get("file") is None:
        raise check.error("missing key 'file' (the panel file)")
    path = folder / check.at("file").string(spec["file"])
    if not path.is_file():
        raise (check.at("file") if isinstance(value, dict) else check).error(
            f"no panel file {path}")
    return PanelBox(path, _rate(spec.get("rate"), check.at("rate"), fps),
                    _freezes(spec.get("freezes"), check.at("freezes")))


def _last_frame(value, check: Checker, folder: Path, fps: int) -> LastFrame:
    return LastFrame(check.string(value))


CONTENT = {"text": _text, "image": _image, "shape": _shape, "shot": _shot, "panel": _panel,
           "last_frame": _last_frame}


def _check_scene(scene: Scene, check: Checker, names: list[str], last: bool) -> None:
    """What a scene can only be checked against the others: its length, its held frames,
    its cross-fade."""
    main = scene.layout.main
    timed = main is not None and main.kind in ("shot", "panel")
    if timed and scene.seconds is not None:
        raise check.at("seconds").error(f"the scene lasts as long as its main box "
                                        f"{main.name!r}; 'seconds' is for a scene of text, "
                                        "pictures or a held frame")
    if not timed and scene.seconds is None:
        raise check.error("missing key 'seconds' (how long the scene is shown: it has no "
                          "shot or panel box to set its length)")
    for i, box in enumerate(scene.layout.boxes):
        if box.kind == "last_frame":
            target = box.content.scene
            if target not in names:
                raise _box_check(scene, check, i, "last_frame").error(
                    f"no scene {target!r} (scenes: {', '.join(names)})")
            if target == scene.name:
                raise _box_check(scene, check, i, "last_frame").error(
                    "a scene cannot hold its own last frame")
        if scene.seconds is not None and box.at is not None:
            start, end = box.at
            if start >= scene.seconds or (end is not None and end > scene.seconds + 1e-9):
                raise _box_check(scene, check, i, "at").error(
                    f"is outside the scene's {scene.seconds:g} seconds")
    if scene.cross and last:
        raise check.at("cross").error("the last scene has no next scene to cross into")
    if scene.cross and scene.fade[1]:
        raise check.at("cross").error("give a fade out or a cross into the next scene, not both")


def _box_check(scene: Scene, check: Checker, index: int, key: str) -> Checker:
    """Where box ``index`` of ``scene`` is written: its layout file, or in place."""
    if scene.layout.file is not None:
        return Checker(scene.layout.file, ("boxes", index, key))
    return check.at("layout", "boxes", index, key)


_BOX_SIZES: dict = {}


def shot_box_size(shot_file) -> tuple[int, int] | None:
    """The size of the shot box that shows the shot file ``shot_file`` in its project's
    film of scenes (``film.yml`` at the project root), the largest when several do;
    ``None`` when no film of scenes shows it (or the film does not load)."""
    from flowreel.project.paths import find_root
    root = find_root(shot_file)
    if root is None or not (root / "film.yml").is_file():
        return None
    path = root / "film.yml"
    stamp = path.stat().st_mtime_ns
    if _BOX_SIZES.get(path, (None,))[0] != stamp:
        sizes: dict = {}
        try:
            film = load(path)
            for scene in film.scenes:
                for box in scene.layout.boxes:
                    if box.kind == "shot" and box.content.file is not None:
                        w, h = box.rect(film.size)[2:]
                        key = Path(box.content.file).resolve()
                        size = (max(round(w), 1), max(round(h), 1))
                        if size[0] * size[1] > sizes.get(key, (0, 0))[0] * sizes.get(key, (0, 0))[1]:
                            sizes[key] = size
        except Exception:                          # a film that does not load sizes nothing
            sizes = {}
        _BOX_SIZES[path] = (stamp, sizes)
    return _BOX_SIZES[path][1].get(Path(shot_file).resolve())
