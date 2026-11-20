"""Captions (plan Section 10.4): the film's words, kept apart from its shot list.

A shot's ``text`` (and a freeze's) is a list of captions, written in place or in a
text file of its own, so the person writing the words never edits ``film.yml``:

.. code-block:: yaml

    # text/domain.yml
    - lines: ['Inlet', 'uniform flow, $U = 1$']
      at: [0.5, 6.5]
      place: [250, 575]
      size: 38
    - lines: ['$Re = 1000$', 'Mass ratio $m^* = 10$']
      at: [1, {shot: bare_reveal, at: 2}]    # runs on across the cut
      place: bottom
      box: true
      shapes:
        - {arrow: {from: [1395, 445], to: [1300, 462]}}

``at`` is ``[start, end]`` in seconds from the start of the finished shot, freezes
included; ``end`` may be left out (to the end of the shot) or be ``{shot: NAME, at:
S}``, a time in a later shot. For a freeze's text, ``at`` counts from the start of the
freeze, and defaults to the freeze less 0.3 s at its start and 0.2 s at its end (the
AFMS film's). Lengths are in pixels of the film, colours are names or ``#rrggbb``.
Anything left out takes the film's caption style.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flowreel.scene.errors import Checker

KEYS = ("lines", "at", "place", "size", "align", "colour", "box", "shadow", "fade",
        "shapes", "id")
PLACES = ("top", "bottom", "centre")
ALIGN = ("centre", "left", "right")
FREEZE_LEAD, FREEZE_TAIL = 0.3, 0.2


@dataclass(frozen=True)
class Later:
    """A time in another shot: ``at`` seconds into the finished shot ``shot``."""

    shot: str
    at: float


@dataclass(frozen=True)
class Caption:
    """One caption.

    ``lines`` of text (``$...$`` is mathematics); ``start`` and ``end`` in seconds of
    the finished shot (``end`` ``None``: to the shot's end, or a :class:`Later`);
    ``place``: ``top``, ``bottom``, ``centre``, ``(x, y)`` (the text's upper left
    corner) or ``("centre", y)`` (centred across, its top at ``y``). ``size`` is the
    letters' height in pixels, ``align`` the lines' alignment, ``colour``, ``box`` (a
    dark panel behind) or ``shadow`` (a soft shadow), ``fade`` in and out in seconds;
    ``None`` takes the film's style. ``shapes`` are its 2D shapes
    (:class:`~flowreel.film.shapes.Shape`); ``id`` names it for other commands.
    """

    lines: tuple[str, ...]
    start: float = 0.0
    end: float | Later | None = None
    place: object = "bottom"
    size: float | None = None
    align: str | None = None
    colour: str | None = None
    box: bool | None = None
    shadow: bool | None = None
    fade: float | None = None
    shapes: tuple = ()
    id: str | None = None


def load_text(path: str | Path) -> list[Caption]:
    """The captions of the text file at ``path`` (a list, includes resolved)."""
    from flowreel.yamlfile import read_yaml
    data = read_yaml(path)
    return parse_captions([] if data is None else data, Checker(path))


def captions_of(value, check: Checker, freeze: float | None = None) -> list[Caption]:
    """The captions of a shot's or freeze's ``text``: a text file's path, a list written
    in place, or ``None``. ``freeze`` is the freeze's hold, for the default ``at``."""
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        from flowreel.yamlfile import read_yaml
        data = read_yaml(value)
        return parse_captions([] if data is None else data, Checker(value), freeze)
    return parse_captions(value, check, freeze)


def parse_captions(value, check: Checker, freeze: float | None = None) -> list[Caption]:
    """A list of caption mappings (one mapping is taken as a list of one)."""
    items = [value] if isinstance(value, dict) else check.sequence(value)
    return [parse_caption(spec, check.at(i) if not isinstance(value, dict) else check, freeze)
            for i, spec in enumerate(items)]


def parse_caption(spec, check: Checker, freeze: float | None = None) -> Caption:
    """One caption mapping (see the module)."""
    from flowreel.compose.style import colour
    spec = check.mapping(spec, KEYS, required=("lines",))
    lines = spec["lines"]
    lines = [lines] if isinstance(lines, str) else check.at("lines").sequence(lines, minimum=1)
    for i, t in enumerate(lines):
        if not isinstance(t, str):
            hint = (" (a line holding ': ' must be quoted: 'Outlet: p = 0')"
                    if isinstance(t, dict) else "")
            raise check.at("lines", i).error(f"expected a line of text, got {t!r}{hint}")
    lines = tuple(lines)
    start, end = _at(spec.get("at"), check.at("at"), freeze)
    size = None if spec.get("size") is None else check.at("size").number(spec["size"])
    if size is not None and size <= 0:
        raise check.at("size").error(f"must be positive, got {size:g}")
    fade = None if spec.get("fade") is None else check.at("fade").number(spec["fade"])
    if fade is not None and fade < 0:
        raise check.at("fade").error(f"must be at least 0, got {fade:g}")
    return Caption(
        lines=lines, start=start, end=end, place=_place(spec.get("place", "bottom"), check.at("place")),
        size=size,
        align=None if spec.get("align") is None else check.at("align").choice(spec["align"], ALIGN),
        colour=None if spec.get("colour") is None else colour(spec["colour"], check.at("colour")),
        box=_flag(spec.get("box"), check.at("box")),
        shadow=_flag(spec.get("shadow"), check.at("shadow")), fade=fade,
        shapes=_shapes(spec.get("shapes"), check.at("shapes")),
        id=None if spec.get("id") is None else check.at("id").string(spec["id"]))


def _flag(value, check: Checker) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise check.error(f"expected true or false, got {value!r}")


def _at(value, check: Checker, freeze: float | None) -> tuple[float, float | Later | None]:
    """``at: [start, end]``, ``at: start``, or left out."""
    if value is None:
        return (FREEZE_LEAD, freeze - FREEZE_TAIL) if freeze is not None else (0.0, None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        items = [value]
    else:
        items = check.sequence(value, minimum=1)
        if len(items) > 2:
            raise check.error(f"expected [start, end], got {len(items)} entries")
    start = check.at(0).number(items[0])
    if start < 0:
        raise check.at(0).error(f"must be at least 0, got {start:g}")
    if len(items) == 1 or items[1] is None:
        end = (freeze - FREEZE_TAIL) if freeze is not None else None
    elif isinstance(items[1], dict):
        if freeze is not None:
            raise check.at(1).error("a freeze's caption ends within the freeze")
        spec = check.at(1).mapping(items[1], ("shot", "at"), required=("shot", "at"))
        when = check.at(1, "at").number(spec["at"])
        if when < 0:
            raise check.at(1, "at").error(f"must be at least 0, got {when:g}")
        end = Later(check.at(1, "shot").string(spec["shot"]), when)
    else:
        end = check.at(1).number(items[1])
        if end <= start:
            raise check.at(1).error(f"the end ({end:g}) must come after the start ({start:g})")
    return start, end


def _place(value, check: Checker):
    if isinstance(value, str):
        return check.choice(value, PLACES)
    if isinstance(value, dict):
        raise check.error("a place in the model ({model: ..., view: ...}) comes with the "
                          "camera editor (Phase 6); give top, bottom, centre or [x, y]")
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected [x, y] or [centre, y], got {len(items)} entries")
    x = items[0] if items[0] == "centre" else check.at(0).number(items[0])
    return (x, check.at(1).number(items[1]))


def _shapes(value, check: Checker) -> tuple:
    from flowreel.film.shapes import parse_shape
    if value is None:
        return ()
    return tuple(parse_shape(spec, check.at(i)) for i, spec in enumerate(check.sequence(value)))
