"""Declared bodies: the ``bodies:`` block of ``flowreel.yml`` (plan Section 5.4).

A source's files say where a body's surface is and nothing else. The declaration adds
what they cannot say: which surface zone it is, the direction of its span, its
reference diameter, how its ends are held and where its time series are.

.. code-block:: yaml

    bodies:
      riser:
        zone: cyl                    # surface zone in the source; default: the body's name
        axis: x                      # span direction; leave out for a body that is not slender
        diameter: 1.0                # reference length; measured from the surface when left out
        ends:
          - {at: 0.0, support: pinned}
          - {at: 500.0, support: roller, free_along: x, tension: true}
        series:
          displacement: {file: data/riser_disp.csv, by: node, stations: data/riser_nodes.csv}

Lengths are in the source's unit. Paths are taken from the folder of ``flowreel.yml``.
The records are plain and frozen; drawing supports and reading series are the jobs of
the ``supports`` layer and the series reader.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.errors import Checker

AXES = ("x", "y", "z")

#: Support kinds and the extra keys each takes (besides ``at``, ``support``, ``tension``).
#: ``roller`` slides along ``free_along``; ``spring`` is held by ``stiffness``;
#: ``free`` is drawn only with ``mark: true``; ``prescribed`` moves along ``direction``.
SUPPORTS: dict[str, tuple[str, ...]] = {
    "clamped": (),
    "pinned": (),
    "roller": ("free_along",),
    "spring": ("stiffness",),
    "free": ("mark",),
    "prescribed": ("direction",),
}
_REQUIRED = {"roller": ("free_along",), "spring": ("stiffness",), "prescribed": ("direction",)}
END_KEYS = ("at", "support", "tension")
BODY_KEYS = ("zone", "axis", "diameter", "ends", "series")
SERIES_KEYS = ("file", "time", "columns", "by", "stations")


@dataclass(frozen=True)
class End:
    """How a body is held at station ``at`` (along the body's axis, source length unit).

    ``support`` is a key of :data:`SUPPORTS`; ``tension`` adds an arrow along the axis;
    ``options`` holds the kind's own keys (``free_along``, ``stiffness``, ``mark``,
    ``direction``).
    """

    at: float
    support: str
    tension: bool = False
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Series:
    """Where a body's time series ``name`` is: a CSV ``file`` (absolute path), its
    ``time`` column, ``columns`` renamed (``{new: column in the file}``), and for a
    history at many points, the column ``by`` that numbers them and their ``stations``
    (a tuple of numbers, or the path of a ``node, station`` CSV)."""

    name: str
    file: Path
    time: str = "time"
    columns: dict = field(default_factory=dict)
    by: str | None = None
    stations: tuple[float, ...] | Path | None = None


@dataclass(frozen=True)
class Body:
    """A declared body: ``name`` as shots use it, the source's surface ``zone``, the span
    ``axis`` (``x``, ``y``, ``z`` or ``None`` for a body that is not slender), the
    reference ``diameter`` (``None``: measured from the surface when needed), its
    ``ends`` and its ``series`` by name."""

    name: str
    zone: str
    axis: str | None = None
    diameter: float | None = None
    ends: tuple[End, ...] = ()
    series: dict = field(default_factory=dict)

    def key(self) -> dict:
        """What the declaration adds to frame keys: zone, axis and diameter (supports and
        series reach a picture through the layers that read them)."""
        return {"zone": self.zone, "axis": self.axis, "diameter": self.diameter}


def parse_bodies(value, check: Checker, folder: Path | None = None) -> dict[str, Body]:
    """The ``bodies:`` mapping as :class:`Body` records by name, checked.

    ``folder`` is where relative series paths are taken from. Raises
    :class:`~flowreel.scene.errors.ConfigError` naming the key path.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise check.error("expected a mapping of body names to declarations")
    bodies: dict[str, Body] = {}
    zones: dict[str, str] = {}
    for name, spec in value.items():
        at = check.at(name)
        if not isinstance(name, str) or not name:
            raise at.error("a body name must be a non-empty string")
        body = _body(name, {} if spec is None else spec, at, folder)
        if body.zone in zones:
            raise at.at("zone").error(f"zone {body.zone!r} is already the body {zones[body.zone]!r}")
        zones[body.zone] = name
        bodies[name] = body
    return bodies


def _body(name: str, spec, check: Checker, folder: Path | None) -> Body:
    spec = check.mapping(spec, BODY_KEYS)
    zone = check.at("zone").string(spec.get("zone", name))
    axis = spec.get("axis")
    if axis is not None:
        axis = check.at("axis").choice(axis, AXES)
    diameter = spec.get("diameter")
    if diameter is not None:
        diameter = check.at("diameter").number(diameter)
        if diameter <= 0:
            raise check.at("diameter").error(f"must be positive, got {diameter:g}")
    ends = tuple(_end(e, check.at("ends", i))
                 for i, e in enumerate(check.at("ends").sequence(spec.get("ends", []))))
    if ends and axis is None:
        raise check.at("ends").error("ends are stations along the body: give the body an 'axis'")
    stations = [e.at for e in ends]
    if len(set(stations)) != len(stations):
        raise check.at("ends").error("two supports at the same station")
    series_spec = spec.get("series") or {}
    if not isinstance(series_spec, dict):
        raise check.at("series").error("expected a mapping of series names to files")
    series = {k: _series(k, v, check.at("series", k), folder) for k, v in series_spec.items()}
    return Body(name, zone, axis, diameter, ends, series)


def _end(spec, check: Checker) -> End:
    if not isinstance(spec, dict) or "support" not in spec:
        raise check.error("expected {at: STATION, support: KIND}")
    kind = check.at("support").choice(spec["support"], list(SUPPORTS))
    spec = check.mapping(spec, END_KEYS + SUPPORTS[kind], required=("at",) + _REQUIRED.get(kind, ()))
    at = check.at("at").number(spec["at"])
    tension = spec.get("tension", False)
    if not isinstance(tension, bool):
        raise check.at("tension").error(f"expected true or false, got {tension!r}")
    options = {}
    if "free_along" in spec:
        options["free_along"] = check.at("free_along").choice(spec["free_along"], AXES)
    if "stiffness" in spec:
        k = check.at("stiffness").number(spec["stiffness"])
        if k <= 0:
            raise check.at("stiffness").error(f"must be positive, got {k:g}")
        options["stiffness"] = k
    if "mark" in spec:
        if not isinstance(spec["mark"], bool):
            raise check.at("mark").error(f"expected true or false, got {spec['mark']!r}")
        options["mark"] = spec["mark"]
    if "direction" in spec:
        d = spec["direction"]
        options["direction"] = (check.at("direction").choice(d, AXES) if isinstance(d, str)
                                else check.at("direction").numbers(d, 3))
    return End(at, kind, tension, options)


def _path(value, check: Checker, folder: Path | None) -> Path:
    path = Path(check.string(value)).expanduser()
    return path if path.is_absolute() or folder is None else Path(folder) / path


def _series(name: str, spec, check: Checker, folder: Path | None) -> Series:
    if isinstance(spec, str):
        spec = {"file": spec}
    spec = check.mapping(spec, SERIES_KEYS, required=("file",))
    columns = spec.get("columns") or {}
    if not isinstance(columns, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                for k, v in columns.items()):
        raise check.at("columns").error("expected a mapping of new names to column names")
    by = spec.get("by")
    if by is not None:
        by = check.at("by").string(by)
    stations = spec.get("stations")
    if stations is not None:
        if by is None:
            raise check.at("stations").error("'stations' places the points of 'by': give 'by'")
        if isinstance(stations, str):
            stations = _path(stations, check.at("stations"), folder)
        else:
            items = check.at("stations").sequence(stations, 1)
            stations = tuple(check.at("stations", i).number(v) for i, v in enumerate(items))
    return Series(name, _path(spec["file"], check.at("file"), folder),
                  check.at("time").string(spec.get("time", "time")), dict(columns), by, stations)
