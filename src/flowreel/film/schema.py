"""The film file (plan Section 10.1): one YAML file describes the whole film.

.. code-block:: yaml

    output: film.mp4
    fps: 24
    size: [1920, 1080]
    style: {font: Lato, colours: {text: '#f2f2f2'}, caption: {size: 50}}
    audio:
      - {file: assets/music.mp3, volume: 0.8, fade: [1.5, 4]}
    watermark: {text: 'A. Periyal', corner: lower_right, size: 24, opacity: 0.6}
    shots:
      - {name: opening, card: cards/opening.yml, seconds: 7, fade: [1.5, 1.5]}
      - {name: domain, frames: frames/bare_domain, fade: [1.5, 0], text: text/domain.yml}
      - name: compare
        layout: compare.yml
        rate: {fps: 8, to_output: interpolate}
        freezes: [{at: 5.0, hold: 6.0, text: text/freeze_motion.yml}]
      - {name: end, hold_last_of: compare, seconds: 13, fade: [0, 2], fade_out_at: 0.5}

Each shot is one of: ``frames`` (a folder of frames), ``layout`` (a layout file, its
``rate: output`` panels drawn at the film's rate), ``card`` (a card file, a still) or
``hold_last_of`` (another shot's last frame, held). Times are in seconds of film
(plan Section 3). Relative paths are taken from the film file's folder.

:func:`load` reads a file, :func:`from_dict` a parsed mapping; both raise
:class:`~flowreel.scene.errors.ConfigError` naming the file and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.errors import Checker

KEYS = ("output", "fps", "size", "style", "audio", "watermark", "shots")
KINDS = ("frames", "layout", "card", "hold_last_of")
SHOT_KEYS = KINDS + ("name", "seconds", "rate", "freezes", "fade", "fade_out_at", "text",
                     "overlays", "chapter")
CHAPTER_KEYS = ("title", "at")
RATE_KEYS = ("fps", "to_output")
TO_OUTPUT = ("interpolate", "repeat", "blend")
FREEZE_KEYS = ("at", "hold", "text")
STYLE_KEYS = ("font", "maths", "colours", "caption")
COLOUR_KEYS = ("text", "muted")
CAPTION_KEYS = ("size", "shadow", "box", "fade", "margin", "align", "spacing")
ALIGN = ("centre", "left", "right")
MATHS = ("font", "dejavusans", "dejavuserif", "cm", "stix", "stixsans")
AUDIO_KEYS = ("file", "offset", "start", "volume", "fade", "licence")
WATERMARK_KEYS = ("image", "text", "corner", "place", "size", "opacity", "colour", "shots",
                  "seconds", "cards")
CORNERS = ("upper_left", "upper_right", "lower_left", "lower_right")
DEFAULT_SIZE = (1920, 1080)


@dataclass(frozen=True)
class CaptionStyle:
    """How captions look unless they say otherwise: letter ``size`` in pixels, a soft
    ``shadow`` or a dark ``box`` behind the text, ``fade`` in and out in seconds,
    ``margin`` from the edge for ``top`` and ``bottom`` in pixels, ``align`` of the
    lines, and line ``spacing`` as a multiple of the size."""

    size: float = 50.0
    shadow: bool = True
    box: bool = False
    fade: float = 0.8
    margin: float = 80.0
    align: str = "centre"
    spacing: float = 1.3


@dataclass(frozen=True)
class FilmStyle:
    """The film's text: ``font`` family (the bundled Lato by default), ``maths`` the
    font of text between ``$`` (``font``: the text's own font, as the AFMS film; or a
    matplotlib maths font set), ``text`` and ``muted`` colours, and the captions'
    defaults."""

    font: str = "Lato"
    maths: str = "font"
    text: str = "#f2f2f2"
    muted: str = "#96a5b2"
    caption: CaptionStyle = field(default_factory=CaptionStyle)


@dataclass(frozen=True)
class Audio:
    """One track: ``file``, from ``offset`` seconds into it, starting ``start`` seconds
    into the film, at ``volume`` (1 as recorded), faded in and out over ``fade``
    seconds; ``licence`` is kept as a note."""

    file: Path
    offset: float = 0.0
    start: float = 0.0
    volume: float = 1.0
    fade: tuple[float, float] = (0.0, 0.0)
    licence: str | None = None


@dataclass(frozen=True)
class Watermark:
    """A signature, logo or watermark (plan Section 10.7): an ``image`` file or a line
    of ``text``, in ``corner`` or with its upper left corner at ``place`` (pixels),
    ``size`` pixels high, at ``opacity``, ``colour`` for text. When: on the shots named
    in ``shots``, or between ``seconds`` of film, or throughout; on cards only when
    ``cards``."""

    image: Path | None = None
    text: str | None = None
    corner: str = "lower_right"
    place: tuple[float, float] | None = None
    size: float = 32.0
    opacity: float = 0.7
    colour: str = "#f2f2f2"
    shots: tuple[str, ...] | None = None
    seconds: tuple[float, float] | None = None
    cards: bool = False


@dataclass(frozen=True)
class Rate:
    """A shot's frame rate: ``fps`` frames of picture a second, made up to the film's
    rate by ``to_output`` (``interpolate``: motion-compensated, ``repeat``: each frame
    shown longer, ``blend``: cross-faded)."""

    fps: float
    to_output: str = "interpolate"


@dataclass(frozen=True)
class Freeze:
    """Stop the shot at ``at`` seconds of its own frames for ``hold`` seconds, with its
    own captions ``text`` (:class:`~flowreel.film.text.Caption`, timed from the start
    of the freeze)."""

    at: float
    hold: float
    text: tuple = ()


@dataclass(frozen=True)
class Chapter:
    """A chapter (plan Section 10.9): ``title``, starting ``at`` seconds into the
    finished shot that names it; it runs until the next chapter or the film's end."""

    title: str
    at: float = 0.0


@dataclass(frozen=True)
class Shot:
    """One shot of the film.

    ``kind`` is ``frames``, ``layout``, ``card`` or ``hold``; ``source`` the frame
    folder, layout file or card file (resolved), or for a hold the name of the shot
    whose last frame it holds (with its ``rate: output`` panels when ``overlays``).
    ``seconds`` is the length of a card or a hold. ``rate``, ``freezes`` belong to frames
    and layout shots. ``fade`` is ``(in, out)`` in seconds, the fade out starting at
    ``fade_out_at`` seconds (default: so that it ends with the shot). ``text`` are its
    captions (:class:`~flowreel.film.text.Caption`), from a text file or written in
    place. ``chapter`` is the :class:`Chapter` the shot starts, or ``None``."""

    name: str
    kind: str
    source: object
    seconds: float | None = None
    rate: Rate | None = None
    freezes: tuple[Freeze, ...] = ()
    fade: tuple[float, float] = (0.0, 0.0)
    fade_out_at: float | None = None
    text: tuple = ()
    overlays: bool = True
    chapter: Chapter | None = None


@dataclass
class Film:
    """A parsed film file: the ``output`` file, ``fps``, picture ``size`` ``(width,
    height)``, ``style``, ``audio`` tracks, ``watermark`` (or ``None``) and ``shots`` in
    order. ``file`` is the film file; relative paths in it start at its folder."""

    output: Path
    fps: int
    size: tuple[int, int]
    shots: list[Shot]
    style: FilmStyle = field(default_factory=FilmStyle)
    audio: tuple[Audio, ...] = ()
    watermark: Watermark | None = None
    file: str | None = None

    @property
    def folder(self) -> Path:
        """Where relative paths in the film file start."""
        return Path(self.file).parent if self.file else Path(".")

    def shot(self, name: str) -> Shot:
        """The shot called ``name``; ``KeyError`` naming the shots otherwise."""
        for s in self.shots:
            if s.name == name:
                return s
        raise KeyError(f"no shot {name!r} (shots: {', '.join(s.name for s in self.shots)})")


def load(path: str | Path) -> Film:
    """Read the film file at ``path``. Errors name the file."""
    from flowreel.yamlfile import read_yaml
    return from_dict(read_yaml(path), file=str(path))


def from_dict(data, file: str | None = None) -> Film:
    """Check ``data`` (a parsed YAML mapping) and build the :class:`Film`."""
    check = Checker(file)
    data = check.mapping(data, KEYS, required=("shots",))
    folder = Path(file).parent if file else Path(".")
    output = folder / check.at("output").string(data.get("output", "film.mp4"))
    fps = check.at("fps").integer(data.get("fps", 24), minimum=1)
    size = _pair(data.get("size", DEFAULT_SIZE), check.at("size"))
    style = _style(data.get("style"), check.at("style"))
    audio = _audio(data.get("audio"), check.at("audio"), folder)
    items = check.at("shots").sequence(data["shots"], minimum=1)
    shots = [_shot(spec, check.at("shots", i), folder, fps) for i, spec in enumerate(items)]
    names = [s.name for s in shots]
    for i, s in enumerate(shots):
        if names.index(s.name) != i:
            raise check.at("shots", i, "name").error(f"shot {s.name!r} is named twice")
    for i, s in enumerate(shots):
        if s.kind == "hold":
            if s.source not in names:
                raise check.at("shots", i, "hold_last_of").error(
                    f"no shot {s.source!r} (shots: {', '.join(names)})")
            target = shots[names.index(s.source)]
            if target.kind not in ("frames", "layout"):
                raise check.at("shots", i, "hold_last_of").error(
                    f"shot {s.source!r} is a {target.kind}; hold the last frame of a frames "
                    "or layout shot")
    watermark = _watermark(data.get("watermark"), check.at("watermark"), folder, names)
    return Film(output, fps, size, shots, style, audio, watermark, file)


def _pair(value, check: Checker) -> tuple[int, int]:
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected [width, height], got {len(items)} entries")
    return tuple(check.at(i).integer(v, minimum=1) for i, v in enumerate(items))


def _colour(value, check: Checker) -> str:
    from flowreel.compose.style import colour
    return colour(value, check)


def _positive(value, check: Checker, zero: bool = True) -> float:
    n = check.number(value)
    if n < 0 or (n == 0 and not zero):
        raise check.error(f"must be {'at least 0' if zero else 'positive'}, got {n:g}")
    return n


def _fade(value, check: Checker) -> tuple[float, float]:
    """``fade: [in, out]`` in seconds, or one number for both."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = _positive(value, check)
        return (v, v)
    a, b = check.numbers(value, 2)
    return (_positive(a, check.at(0)), _positive(b, check.at(1)))


def _style(value, check: Checker) -> FilmStyle:
    spec = check.mapping(value or {}, STYLE_KEYS)
    base = FilmStyle()
    colours = check.at("colours").mapping(spec.get("colours") or {}, COLOUR_KEYS)
    cap = check.at("caption").mapping(spec.get("caption") or {}, CAPTION_KEYS)
    c = CaptionStyle()
    caption = CaptionStyle(
        size=_positive(cap.get("size", c.size), check.at("caption", "size"), zero=False),
        shadow=_bool(cap.get("shadow", c.shadow), check.at("caption", "shadow")),
        box=_bool(cap.get("box", c.box), check.at("caption", "box")),
        fade=_positive(cap.get("fade", c.fade), check.at("caption", "fade")),
        margin=_positive(cap.get("margin", c.margin), check.at("caption", "margin")),
        align=check.at("caption", "align").choice(cap.get("align", c.align), ALIGN),
        spacing=_positive(cap.get("spacing", c.spacing), check.at("caption", "spacing"),
                          zero=False))
    return FilmStyle(
        font=check.at("font").string(spec.get("font", base.font)),
        maths=check.at("maths").choice(spec.get("maths", base.maths), MATHS),
        text=_colour(colours.get("text", base.text), check.at("colours", "text")),
        muted=_colour(colours.get("muted", base.muted), check.at("colours", "muted")),
        caption=caption)


def _bool(value, check: Checker) -> bool:
    if not isinstance(value, bool):
        raise check.error(f"expected true or false, got {value!r}")
    return value


def _audio(value, check: Checker, folder: Path) -> tuple[Audio, ...]:
    if value is None:
        return ()
    items = [value] if isinstance(value, dict) else check.sequence(value)
    out = []
    for i, spec in enumerate(items):
        at = check if isinstance(value, dict) else check.at(i)
        spec = at.mapping(spec, AUDIO_KEYS, required=("file",))
        volume = _positive(spec.get("volume", 1.0), at.at("volume"))
        out.append(Audio(
            file=folder / at.at("file").string(spec["file"]),
            offset=_positive(spec.get("offset", 0.0), at.at("offset")),
            start=_positive(spec.get("start", 0.0), at.at("start")),
            volume=volume, fade=_fade(spec.get("fade", [0, 0]), at.at("fade")),
            licence=None if spec.get("licence") is None else at.at("licence").string(spec["licence"])))
    return tuple(out)


def _watermark(value, check: Checker, folder: Path, names: list[str]) -> Watermark | None:
    if value is None:
        return None
    w = parse_watermark(value, check, folder)
    if w.shots is not None:
        for k, name in enumerate(w.shots):
            if name not in names:
                raise check.at("shots", k).error(f"no shot {name!r} (shots: {', '.join(names)})")
    return w


#: Keys of a film's watermark only: when it shows.
WHEN_KEYS = ("shots", "seconds", "cards")


def parse_watermark(value, check: Checker, folder: Path, shot: bool = False) -> Watermark:
    """A ``watermark`` mapping (plan Section 10.7): the film's, or a shot file's when
    ``shot`` (drawn into every frame, so without ``shots``, ``seconds`` or ``cards``).
    An ``image`` is taken from ``folder`` and must exist."""
    spec = check.mapping(value, tuple(k for k in WATERMARK_KEYS if not (shot and k in WHEN_KEYS)))
    given = [k for k in ("image", "text") if spec.get(k) is not None]
    if len(given) != 1:
        raise check.error("give one of 'image' (a file) or 'text' (a line of text)")
    image = None
    if spec.get("image") is not None:
        image = folder / check.at("image").string(spec["image"])
        if not image.is_file():
            raise check.at("image").error(f"no image file {image}")
    if "corner" in spec and "place" in spec:
        raise check.at("place").error("give 'corner' or 'place', not both")
    opacity = check.at("opacity").number(spec.get("opacity", Watermark.opacity))
    if not 0 <= opacity <= 1:
        raise check.at("opacity").error(f"expected 0 to 1, got {opacity:g}")
    seconds = None
    if spec.get("seconds") is not None:
        a, b = check.at("seconds").numbers(spec["seconds"], 2)
        if not 0 <= a < b:
            raise check.at("seconds").error(f"expected [start, end] with 0 <= start < end, "
                                            f"got [{a:g}, {b:g}]")
        seconds = (a, b)
    shots = None
    if spec.get("shots") is not None:
        if seconds is not None:
            raise check.at("shots").error("give 'shots' or 'seconds', not both")
        shots = tuple(check.at("shots", k).string(s)
                      for k, s in enumerate(check.at("shots").sequence(spec["shots"], minimum=1)))
    return Watermark(
        image=image,
        text=None if spec.get("text") is None else check.at("text").string(spec["text"]),
        corner=check.at("corner").choice(spec.get("corner", Watermark.corner), CORNERS),
        place=None if spec.get("place") is None else check.at("place").numbers(spec["place"], 2),
        size=_positive(spec.get("size", Watermark.size), check.at("size"), zero=False),
        opacity=opacity, colour=_colour(spec.get("colour", Watermark.colour), check.at("colour")),
        shots=shots, seconds=seconds, cards=_bool(spec.get("cards", False), check.at("cards")))


def _shot(spec, check: Checker, folder: Path, film_fps: int) -> Shot:
    spec = check.mapping(spec, SHOT_KEYS, required=("name",))
    name = check.at("name").string(spec["name"])
    given = [k for k in KINDS if k in spec]
    if len(given) != 1:
        raise check.error("give one of 'frames' (a folder of frames), 'layout' (a layout "
                          "file), 'card' (a card file) or 'hold_last_of' (a shot's name)")
    kind = given[0]
    still = kind in ("card", "hold_last_of")
    for key in ("rate", "freezes"):
        if still and key in spec:
            raise check.at(key).error(f"a {kind.replace('_last_of', '')} is a still; "
                                      f"'{key}' is for frames and layout shots")
    if not still and "seconds" in spec:
        raise check.at("seconds").error("a frames or layout shot lasts as long as its frames "
                                        "(and freezes); 'seconds' is for cards and holds")
    if still and "seconds" not in spec:
        raise check.error("missing key 'seconds' (how long the still is shown)")
    if "overlays" in spec and kind != "hold_last_of":
        raise check.at("overlays").error("is used only with 'hold_last_of'")
    value = check.at(kind).string(spec[kind])
    source = value if kind == "hold_last_of" else folder / value
    if kind in ("layout", "card") and not source.is_file():
        raise check.at(kind).error(f"no {kind} file {source}")
    rate = None if still else _rate(spec.get("rate"), check.at("rate"), film_fps)
    freezes = () if still else _freezes(spec.get("freezes"), check.at("freezes"), folder)
    fade = _fade(spec.get("fade", [0, 0]), check.at("fade"))
    fade_out_at = None if spec.get("fade_out_at") is None else \
        _positive(spec["fade_out_at"], check.at("fade_out_at"))
    if fade_out_at is not None and not fade[1]:
        raise check.at("fade_out_at").error("is used only with a fade out (fade: [in, out])")
    seconds = None if not still else _positive(spec["seconds"], check.at("seconds"), zero=False)
    return Shot(name, "hold" if kind == "hold_last_of" else kind, source, seconds, rate, freezes,
                fade, fade_out_at, _text(spec.get("text"), check.at("text"), folder),
                _bool(spec.get("overlays", True), check.at("overlays")),
                _chapter(spec.get("chapter"), check.at("chapter")))


def _chapter(value, check: Checker) -> Chapter | None:
    """``chapter: TITLE`` or ``{title: TITLE, at: S}``."""
    if value is None:
        return None
    if isinstance(value, str):
        title, at, where = value, 0.0, check
    else:
        spec = check.mapping(value, CHAPTER_KEYS, required=("title",))
        where = check.at("title")
        title, at = where.string(spec["title"]), _positive(spec.get("at", 0.0), check.at("at"))
    title = title.strip()
    if not title or "\n" in title:
        raise where.error("a chapter's title is one line of text")
    return Chapter(title, at)


def _text(value, check: Checker, folder: Path, freeze: float | None = None) -> tuple:
    """The captions of a ``text``: a text file (from ``folder``), a list written in
    place, or none. ``freeze`` is a freeze's hold, for its captions' default times."""
    from flowreel.film.text import captions_of
    if value is None:
        return ()
    if isinstance(value, str):
        path = folder / value
        if not path.is_file():
            raise check.error(f"no text file {path}")
        value = path
    return tuple(captions_of(value, check, freeze))


def _rate(value, check: Checker, film_fps: int) -> Rate:
    """``rate: {fps, to_output}``; ``fps`` must divide the film's rate."""
    spec = check.mapping(value or {}, RATE_KEYS)
    fps = check.at("fps").number(spec.get("fps", film_fps))
    if fps <= 0 or fps > film_fps:
        raise check.at("fps").error(f"expected more than 0 and at most the film's {film_fps}, "
                                    f"got {fps:g}")
    ratio = film_fps / fps
    if abs(ratio - round(ratio)) > 1e-9:
        raise check.at("fps").error(f"the film's {film_fps} frames a second must be a whole "
                                    f"number of the shot's {fps:g} (such as 8 in 24)")
    return Rate(fps, check.at("to_output").choice(spec.get("to_output", "interpolate"), TO_OUTPUT))


def _freezes(value, check: Checker, folder: Path) -> tuple[Freeze, ...]:
    items = check.sequence(value or [])
    out = []
    for i, spec in enumerate(items):
        at = check.at(i)
        spec = at.mapping(spec, FREEZE_KEYS, required=("at", "hold"))
        hold = _positive(spec["hold"], at.at("hold"), zero=False)
        out.append(Freeze(_positive(spec["at"], at.at("at")), hold,
                          _text(spec.get("text"), at.at("text"), folder, freeze=hold)))
    ats = [f.at for f in out]
    if ats != sorted(ats):
        raise check.error("freezes must be in order of 'at'")
    return tuple(out)
