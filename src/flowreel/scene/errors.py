"""Validation helpers shared by every YAML file type (plan Section 15).

Errors name the file and the key path, say what was expected and, for an unknown key,
suggest the nearest valid one. A path is a tuple such as ``("layers", 2, "level")`` and is
printed as ``layers[2].level``.
"""
from __future__ import annotations

import difflib
from collections.abc import Mapping
from pathlib import Path


class ConfigError(ValueError):
    """A problem in a YAML file: ``file: key.path: what is wrong``."""

    def __init__(self, message: str, file: str | Path | None = None, path: tuple = ()):
        self.file = None if file is None else str(file)
        self.path = tuple(path)
        self.problem = message
        super().__init__(self._text())

    def _text(self) -> str:
        head = ": ".join(p for p in (self.file, format_path(self.path)) if p)
        return f"{head}: {self.problem}" if head else self.problem


def format_path(path: tuple) -> str:
    """Print ``("layers", 2, "level")`` as ``layers[2].level``."""
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


class Checker:
    """Reads one YAML file's values and raises :class:`ConfigError` that name the place.

    ``file`` is the file name shown in messages (``None`` for an in-memory dict).
    :meth:`at` returns a checker for a nested key or list index, so the path grows as
    the reader descends.
    """

    def __init__(self, file: str | Path | None = None, path: tuple = ()):
        self.file = file
        self.path = tuple(path)

    def at(self, *keys) -> "Checker":
        """A checker for the nested ``keys`` below this one."""
        return Checker(self.file, self.path + keys)

    def error(self, message: str) -> ConfigError:
        """Build (do not raise) an error at this path."""
        return ConfigError(message, self.file, self.path)

    def mapping(self, value, allowed, required=()) -> dict:
        """Check ``value`` is a mapping with only ``allowed`` keys and all ``required``.

        An unknown key is reported with the nearest allowed one when there is a close
        match. Returns ``value`` as a dict.
        """
        if not isinstance(value, Mapping):
            raise self.error(f"expected a mapping, got {_describe(value)}")
        for key in value:
            if key not in allowed:
                raise self.at(key).error(unknown_key_message(key, allowed))
        for key in required:
            if key not in value:
                raise self.error(f"missing key {key!r}")
        return dict(value)

    def sequence(self, value, minimum: int = 0) -> list:
        """Check ``value`` is a list with at least ``minimum`` entries."""
        if not isinstance(value, (list, tuple)):
            raise self.error(f"expected a list, got {_describe(value)}")
        if len(value) < minimum:
            raise self.error(f"expected at least {minimum} entries, got {len(value)}")
        return list(value)

    def choice(self, value, allowed):
        """Check ``value`` is one of ``allowed`` (suggests the nearest on a typo)."""
        if value not in allowed:
            hint = _nearest(value, allowed)
            extra = f"; did you mean {hint!r}?" if hint else ""
            raise self.error(f"{value!r} is not allowed (one of: "
                             f"{', '.join(map(str, allowed))}){extra}")
        return value

    def string(self, value) -> str:
        """Check ``value`` is a non-empty string."""
        if not isinstance(value, str) or not value:
            raise self.error(f"expected a non-empty string, got {_describe(value)}")
        return value

    def integer(self, value, minimum: int | None = None) -> int:
        """Check ``value`` is a whole number, at least ``minimum`` when given."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise self.error(f"expected a whole number, got {_describe(value)}")
        if minimum is not None and value < minimum:
            raise self.error(f"must be at least {minimum}, got {value}")
        return value

    def number(self, value) -> float:
        """Check ``value`` is a finite number."""
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or value != value or abs(value) == float("inf"):
            raise self.error(f"expected a number, got {_describe(value)}")
        return float(value)

    def numbers(self, value, count: int) -> tuple[float, ...]:
        """Check ``value`` is a list of exactly ``count`` numbers."""
        items = self.sequence(value)
        if len(items) != count:
            raise self.error(f"expected {count} numbers, got {len(items)}")
        return tuple(self.at(i).number(v) for i, v in enumerate(items))

    def wrap(self, exc: ValueError) -> ConfigError:
        """Turn a ``ValueError`` from a lower layer (tracks) into an error at this path."""
        return self.error(str(exc))


def unknown_key_message(key, allowed) -> str:
    """Text for an unknown key, with the nearest valid key when one is close."""
    hint = _nearest(key, allowed)
    extra = f"; did you mean {hint!r}?" if hint else ""
    return f"unknown key {key!r} (allowed: {', '.join(map(str, allowed))}){extra}"


def _nearest(value, allowed) -> str | None:
    if not isinstance(value, str):
        return None
    close = difflib.get_close_matches(value, [str(a) for a in allowed], n=1, cutoff=0.6)
    return close[0] if close else None


def _describe(value) -> str:
    if isinstance(value, Mapping):
        return "a mapping"
    if isinstance(value, (list, tuple)):
        return "a list"
    return repr(value)
