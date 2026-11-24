"""The pieces a film file and a shot file share (plan Section 10.1): the film's size and
rate defaults, the audio tracks, the watermark, chapters and rates, with their keys.

:mod:`flowreel.film.model` reads a film of scenes with these. :func:`parse_watermark`
reads a ``watermark`` mapping, the film's or a shot file's. Each parser raises
:class:`~flowreel.scene.errors.ConfigError` naming the file and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flowreel.scene.errors import Checker

CHAPTER_KEYS = ("title", "at")
RATE_KEYS = ("fps", "to_output")
TO_OUTPUT = ("interpolate", "repeat", "blend")
ALIGN = ("centre", "left", "right")
MATHS = ("font", "dejavusans", "dejavuserif", "cm", "stix", "stixsans")
AUDIO_KEYS = ("file", "offset", "start", "volume", "fade", "licence")
WATERMARK_KEYS = ("image", "text", "corner", "place", "size", "opacity", "colour", "shots",
                  "seconds", "cards")
CORNERS = ("upper_left", "upper_right", "lower_left", "lower_right")
DEFAULT_SIZE = (1920, 1080)
#: Keys of a film's watermark only: when it shows.
WHEN_KEYS = ("shots", "seconds", "cards")


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
class Chapter:
    """A chapter (plan Section 10.9): ``title``, starting ``at`` seconds into the
    finished shot that names it; it runs until the next chapter or the film's end."""

    title: str
    at: float = 0.0


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
