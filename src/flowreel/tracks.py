"""Tracks: values that change with the frame number (plan Section 7.3).

A track is built from one of three YAML forms, already parsed into Python objects::

    opacity: 1.0                                           # fixed
    position: {from: 0.02, to: 6.0, frames: [48, 72]}      # two keys, eased
    grey: {keys: [[0, 0], [58, 0], [72, 1]]}               # any number of keys
    level: {keys: [[0, -0.1], [120, -1.0]], ease: out}

Use :func:`parse` to build a :class:`Track`. Malformed specs raise ``ValueError`` with the
track's name and the offending key, so the message can be shown to the user as it is.
"""
from __future__ import annotations

import math
import re
from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real


def _linear(t: float) -> float:
    return t


def _smooth(t: float) -> float:
    # Smoothstep, written as in the prototype's ramp() so the values match bit for bit.
    return t * t * (3 - 2 * t)


def _in(t: float) -> float:
    return t * t * t


def _out(t: float) -> float:
    u = 1 - t
    return 1 - u * u * u


def _in_out(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    u = 2 - 2 * t
    return 1 - u * u * u / 2


def _hold(t: float) -> float:
    return 1.0 if t >= 1 else 0.0


EASINGS = {
    "linear": _linear,    # constant rate
    "smooth": _smooth,    # smoothstep 3t^2 - 2t^3: zero slope at both ends
    "in": _in,            # cubic t^3: starts slowly
    "out": _out,          # cubic 1 - (1 - t)^3: ends slowly
    "in_out": _in_out,    # cubic, slow at both ends, steeper than smooth in the middle
    "hold": _hold,        # steps: keeps the earlier value until the next key
}
EASE_NAMES = tuple(EASINGS)

# Section 7.3 calls the two-key form "eased" without naming an ease, and the prototype
# eased every move with smoothstep, so a track with no ``ease`` uses ``smooth``.
DEFAULT_EASE = "smooth"


def ease(name: str, t: float) -> float:
    """Return the eased fraction for ``t``, the fraction of the way between two keys.

    ``name`` is one of ``EASE_NAMES``. ``t`` is clamped to 0..1, and every easing returns
    0 at ``t = 0`` and 1 at ``t = 1``. Raises ``ValueError`` for an unknown name.
    """
    if name not in EASINGS:
        raise ValueError(f"unknown ease {name!r} (allowed: {', '.join(EASE_NAMES)})")
    return EASINGS[name](min(max(t, 0.0), 1.0))


KINDS = ("number", "vector", "colour", "boolean", "choice")
STEPPED = ("boolean", "choice")
"""Kinds that cannot be interpolated: they switch at each key."""

_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
_SPEC_KEYS = ("from", "to", "frames", "keys", "ease")
_TWO_KEY_FORM = ("from", "to", "frames")


@dataclass(frozen=True)
class Track:
    """A value keyed on frame numbers.

    ``frames`` are strictly increasing; ``values`` has one entry per frame; ``ease`` is the
    easing used between neighbouring keys; ``kind`` is the value type; ``name`` is used in
    error messages. A fixed value is a track with a single key. Build with :func:`parse`.
    """

    frames: tuple[float, ...]
    values: tuple
    ease: str = DEFAULT_EASE
    kind: str = "number"
    name: str = "track"

    @property
    def fixed(self) -> bool:
        """True when the track has one value for every frame."""
        return all(v == self.values[0] for v in self.values)

    def at(self, frame: float):
        """Return the value at ``frame`` (whole or fractional).

        Before the first key the track holds the first value, after the last key the
        last. On a key it returns that key's value exactly. Numbers come back as floats,
        vectors and colours (sRGB, 0..1) as tuples of floats.
        """
        frames = self.frames
        if frame <= frames[0]:
            return self.values[0]
        if frame >= frames[-1]:
            return self.values[-1]
        i = bisect_right(frames, frame) - 1
        t = (frame - frames[i]) / (frames[i + 1] - frames[i])
        return blend(self.kind, self.values[i], self.values[i + 1],
                     EASINGS[self.ease](t))

    __call__ = at


def parse(spec, kind: str | None = None, name: str = "track",
          default_ease: str = DEFAULT_EASE) -> Track:
    """Build a :class:`Track` from a parsed YAML value.

    ``spec`` is a fixed value, ``{from, to, frames: [start, end]}`` or
    ``{keys: [[frame, value], ...]}``, the last two with an optional ``ease``.
    ``kind`` is one of ``KINDS``. Leave it ``None`` to infer the kind from the values:
    booleans, numbers, lists of numbers (vector), hex strings (colour), other strings
    (choice). Pass ``"colour"`` where the option is a colour, so that RGB lists are read
    as colours and not as vectors.
    ``name`` is the YAML key the spec came from and starts every error message.
    ``default_ease`` is used when the spec has no ``ease``.
    Raises ``ValueError`` for a malformed spec.
    """
    if kind is not None and kind not in KINDS:
        raise ValueError(f"{name}: unknown kind {kind!r} (allowed: {', '.join(KINDS)})")
    if isinstance(spec, Track):
        return spec
    if not isinstance(spec, Mapping):
        frames, raw, ease_name = (0.0,), [spec], None
    else:
        unknown = [k for k in spec if k not in _SPEC_KEYS]
        if unknown:
            raise ValueError(f"{name}: unknown key {unknown[0]!r} "
                             f"(allowed: {', '.join(_SPEC_KEYS)})")
        two_key = [k for k in _TWO_KEY_FORM if k in spec]
        if "keys" in spec and two_key:
            raise ValueError(f"{name}: 'keys' cannot be combined with {two_key[0]!r}; "
                             "use either keys or from/to/frames")
        if "keys" in spec:
            frames, raw = _read_keys(spec["keys"], name)
        elif two_key:
            missing = [k for k in _TWO_KEY_FORM if k not in spec]
            if missing:
                raise ValueError(f"{name}: missing key {missing[0]!r}; "
                                 "the two-key form needs from, to and frames")
            pair = spec["frames"]
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"{name}: 'frames' must be [start, end], got {pair!r}")
            frames = _read_frames(pair, "frames", name)
            raw = [spec["from"], spec["to"]]
        else:
            raise ValueError(f"{name}: needs 'keys' or from/to/frames, got only "
                             f"{sorted(spec) or 'an empty mapping'}")
        ease_name = spec.get("ease")
    if ease_name is not None and ease_name not in EASE_NAMES:
        raise ValueError(f"{name}: unknown ease {ease_name!r} "
                         f"(allowed: {', '.join(EASE_NAMES)})")
    kind, values = _read_values(raw, kind, name)
    if kind in STEPPED:
        if ease_name not in (None, "hold"):
            raise ValueError(f"{name}: ease {ease_name!r} cannot be used with {kind} "
                             "values; they step from key to key (ease: hold)")
        ease_name = "hold"
    return Track(frames=frames, values=values, ease=ease_name or default_ease,
                 kind=kind, name=name)


def _read_keys(keys, name: str):
    """Split ``[[frame, value], ...]`` into checked frames and raw values."""
    if not isinstance(keys, (list, tuple)) or not keys:
        raise ValueError(f"{name}: 'keys' must be a list of [frame, value] pairs, "
                         f"got {keys!r}")
    for key in keys:
        if not isinstance(key, (list, tuple)) or len(key) != 2:
            raise ValueError(f"{name}: each entry of 'keys' must be [frame, value], "
                             f"got {key!r}")
    return _read_frames([k[0] for k in keys], "keys", name), [k[1] for k in keys]


def _read_frames(frames, key: str, name: str) -> tuple[float, ...]:
    """Check that frames are finite numbers in strictly increasing order."""
    for f in frames:
        if isinstance(f, bool) or not isinstance(f, Real) or not math.isfinite(f):
            raise ValueError(f"{name}: frame {f!r} in {key!r} is not a number")
    for a, b in zip(frames, frames[1:]):
        if b == a:
            raise ValueError(f"{name}: frame {a} appears twice in {key!r}")
        if b < a:
            raise ValueError(f"{name}: frames in {key!r} must increase, "
                             f"but {b} follows {a}")
    return tuple(frames)


def _read_values(raw, kind: str | None, name: str) -> tuple[str, tuple]:
    """Find the kind of the values (unless given) and convert them to it."""
    if kind is None:
        kinds = [_kind_of(v, name) for v in raw]
        for other in kinds[1:]:
            if other != kinds[0]:
                raise ValueError(f"{name}: mixed value types ({kinds[0]} and {other}); "
                                 "every key needs the same type")
        kind = kinds[0]
    values = tuple(_CONVERT[kind](v, name) for v in raw)
    if kind == "vector":
        for v in values[1:]:
            if len(v) != len(values[0]):
                raise ValueError(f"{name}: mixed value types (vectors of {len(values[0])} "
                                 f"and {len(v)} components)")
    return kind, values


def _is_number(value) -> bool:
    return (not isinstance(value, bool) and isinstance(value, Real)
            and math.isfinite(value))


def _kind_of(value, name: str) -> str:
    """Infer the kind of one raw value."""
    if isinstance(value, bool):
        return "boolean"
    if _is_number(value):
        return "number"
    if isinstance(value, str):
        return "colour" if _HEX.match(value) else "choice"
    if isinstance(value, (list, tuple)) and value and all(_is_number(c) for c in value):
        return "vector"
    raise ValueError(f"{name}: cannot use {value!r} as a track value")


def _number(value, name: str) -> float:
    if not _is_number(value):
        raise ValueError(f"{name}: expected a number, got {value!r}")
    return float(value)


def _vector(value, name: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or not value \
            or not all(_is_number(c) for c in value):
        raise ValueError(f"{name}: expected a list of numbers, got {value!r}")
    return tuple(float(c) for c in value)


def _colour(value, name: str) -> tuple[float, float, float]:
    try:
        return parse_colour(value)
    except ValueError as err:
        raise ValueError(f"{name}: {err}") from None


def _boolean(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name}: expected true or false, got {value!r}")
    return value


def _choice(value, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}: expected a name (text), got {value!r}")
    return value


_CONVERT = {"number": _number, "vector": _vector, "colour": _colour,
            "boolean": _boolean, "choice": _choice}


def parse_colour(value) -> tuple[float, float, float]:
    """Read a colour as an sRGB tuple of three floats in 0..1.

    Accepts a hex string (``"#rgb"`` or ``"#rrggbb"``) or three numbers in 0..1
    (not 0..255). Raises ``ValueError`` for anything else.
    """
    if isinstance(value, str):
        if not _HEX.match(value):
            raise ValueError(f"expected a colour as '#rgb' or '#rrggbb', got {value!r}")
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(d * 2 for d in digits)
        return tuple(int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))
    if isinstance(value, (list, tuple)) and len(value) == 3 \
            and all(_is_number(c) and 0 <= c <= 1 for c in value):
        return tuple(float(c) for c in value)
    raise ValueError("expected a colour as a hex string or three numbers in 0..1, "
                     f"got {value!r}")


def srgb_to_linear(c: float) -> float:
    """Decode one sRGB channel (0..1) to linear light (IEC 61966-2-1)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """Encode one linear-light channel (0..1) as sRGB (IEC 61966-2-1)."""
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def blend(kind: str, a, b, t: float):
    """Return the value a fraction ``t`` (0..1, already eased) of the way from ``a`` to ``b``.

    Numbers and vectors are interpolated; colours (sRGB tuples) are decoded, interpolated
    in linear RGB and encoded again, which avoids the dark band a blend of sRGB values
    gives. Booleans and choices cannot be interpolated: ``a`` holds until ``t`` reaches 1.
    ``t = 0`` and ``t = 1`` return ``a`` and ``b`` exactly.
    """
    if t <= 0:
        return a
    if t >= 1:
        return b
    if kind in STEPPED:
        return a
    if kind == "number":
        return a + (b - a) * t
    if kind == "vector":
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    if kind == "colour":
        mixed = (x + (y - x) * t for x, y in zip(map(srgb_to_linear, a),
                                                 map(srgb_to_linear, b)))
        return tuple(linear_to_srgb(c) for c in mixed)
    raise ValueError(f"unknown kind {kind!r} (allowed: {', '.join(KINDS)})")


class TimeTrack:
    """The ``time`` track of a shot: maps frames to simulation steps.

    ``time: {keys: [[0, 5000], [120, 5300]]}`` runs from step 5000 at frame 0 to step
    5300 at frame 120; a fixed ``time: 5000`` freezes the flow. Unlike other tracks the
    default ease is ``linear``, so that flow time advances at a constant rate unless the
    spec asks otherwise. Outside the keys the step is clamped like any track.
    """

    def __init__(self, spec, name: str = "time"):
        self.track = parse(spec, kind="number", name=name, default_ease="linear")

    def at(self, frame: float) -> float:
        """Return the step asked for at ``frame``, possibly between saved steps."""
        return self.track.at(frame)

    def step(self, frame: float, steps):
        """Return the saved step nearest to the one asked for at ``frame``.

        ``steps`` are the saved step numbers (``Source.steps()``). See
        :func:`nearest_step` for the tie rule.
        """
        return nearest_step(self.at(frame), steps)


def nearest_step(value: float, steps):
    """Return the entry of ``steps`` nearest to ``value``; fields are never interpolated.

    ``steps`` are the saved step numbers in any order. A value exactly halfway between
    two saved steps takes the earlier one, so a frame never shows the flow later than
    the time asked for. Values outside the saved range take the first or last step.
    Raises ``ValueError`` when ``steps`` is empty.
    """
    ordered = sorted(steps)
    if not ordered:
        raise ValueError("no saved steps to choose from")
    i = bisect_left(ordered, value)
    if i == 0:
        return ordered[0]
    if i == len(ordered):
        return ordered[-1]
    lo, hi = ordered[i - 1], ordered[i]
    return lo if value - lo <= hi - value else hi
