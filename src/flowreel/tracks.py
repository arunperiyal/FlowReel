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
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real

EASE_NAMES = ("linear", "smooth", "in", "out", "in_out", "hold")
DEFAULT_EASE = "smooth"

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


def parse(spec, name: str = "track", default_ease: str = DEFAULT_EASE) -> Track:
    """Build a :class:`Track` from a parsed YAML value.

    ``spec`` is a fixed value, ``{from, to, frames: [start, end]}`` or
    ``{keys: [[frame, value], ...]}``, the last two with an optional ``ease``.
    ``name`` is the YAML key the spec came from and starts every error message.
    ``default_ease`` is used when the spec has no ``ease``.
    Raises ``ValueError`` for a malformed spec.
    """
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
    values = _read_values(raw, name)
    return Track(frames=frames, values=values, ease=ease_name or default_ease, name=name)


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


def _read_values(raw, name: str) -> tuple:
    """Check the values of the keys and convert them to floats."""
    for v in raw:
        if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v):
            raise ValueError(f"{name}: cannot use {v!r} as a track value")
    return tuple(float(v) for v in raw)
