"""Declared bodies: the ``bodies:`` block of ``flowreel.yml`` (plan Section 5.4).

A source's files say where a body's surface is and nothing else. The declaration adds
what they cannot say: which surface zone it is and where its time series are, and for a
**beam body** (a slender one, with an ``axis``) the direction of its span, its
reference diameter and how its ends are held.

.. code-block:: yaml

    bodies:
      riser:
        zone: cyl                    # surface zone in the source; default: the body's name
        axis: x                      # span direction; leave out for a body that is not slender
        diameter: 1.0                # beam bodies only; measured from the surface when left out
        ends:
          - {at: 0.0, support: pinned}
          - {at: 500.0, support: roller, free_along: x, tension: true}
        series:
          displacement: {file: data/riser_disp.csv, by: node, stations: data/riser_nodes.csv}

A **virtual body** (``virtual: true``) has no surface in the files: it is modelled by
the solver as equations (a pendulum, a spring) and drawn from a registered ``shape``
(a body function of :mod:`flowreel.sources.bodies`) with fixed ``params`` and
parameters ``drive``-n by series tracks, its origin ``attach``-ed to a real body at a
station or to a fixed point (plan Section 5.5).

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
#: Keys each support kind must be given.
REQUIRED = {"roller": ("free_along",), "spring": ("stiffness",), "prescribed": ("direction",)}
END_KEYS = ("at", "support", "tension")
BODY_KEYS = ("zone", "axis", "diameter", "ends", "series")
VIRTUAL_KEYS = ("virtual", "shape", "params", "attach", "drive", "series")
ATTACH_KEYS = ("body", "station", "point", "offset")
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
class Attach:
    """Where a virtual body's origin is: on ``body``'s centre at ``station`` (the body's
    centre when no station), or at a fixed ``point``; then moved by ``offset``."""

    body: str | None = None
    station: float | None = None
    point: tuple[float, float, float] | None = None
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class Body:
    """A declared body: ``name`` as shots use it, the source's surface ``zone``, the span
    ``axis`` (``x``, ``y``, ``z``, making it a beam body; ``None`` for a body that is not
    slender), the reference ``diameter`` of a beam body (``None``: measured from the
    surface when needed), its ``ends`` (beam bodies only) and its ``series`` by name."""

    name: str
    zone: str | None
    axis: str | None = None
    diameter: float | None = None
    ends: tuple[End, ...] = ()
    series: dict = field(default_factory=dict)
    virtual: bool = False
    shape: str | None = None
    params: dict = field(default_factory=dict)
    attach: Attach | None = None
    drive: dict = field(default_factory=dict)

    def key(self) -> dict:
        """What the declaration adds to frame keys: zone, axis and diameter (supports and
        series reach a picture through the layers that read them); for a virtual body,
        its shape, parameters, attachment and drives."""
        if self.virtual:
            from dataclasses import asdict
            return {"shape": self.shape, "params": self.params, "drive": self.drive,
                    "attach": None if self.attach is None else asdict(self.attach)}
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
        spec = {} if spec is None else spec
        if isinstance(spec, dict) and spec.get("virtual") is not None:
            bodies[name] = _virtual(name, spec, at, folder)
            continue
        body = _body(name, spec, at, folder)
        if body.zone in zones:
            raise at.at("zone").error(f"zone {body.zone!r} is already the body {zones[body.zone]!r}")
        zones[body.zone] = name
        bodies[name] = body
    for name, body in bodies.items():
        if body.virtual and body.attach is not None and body.attach.body is not None:
            _check_attach(body.attach, bodies, check.at(name, "attach"))
    return bodies


def _virtual(name: str, spec, check: Checker, folder: Path | None) -> Body:
    """A virtual body: no surface in the files, drawn from a registered ``shape``."""
    import inspect

    from flowreel.sources.bodies import available_bodies, get_body
    from flowreel.tracks import SeriesTrack
    spec = check.mapping(spec, VIRTUAL_KEYS, required=("shape",))
    if spec["virtual"] is not True:
        raise check.at("virtual").error("write virtual: true, or leave the key out for a "
                                        "body with a surface in the files")
    shape = check.at("shape").choice(spec["shape"], available_bodies())
    params = spec.get("params") or {}
    if not isinstance(params, dict):
        raise check.at("params").error("expected a mapping of the shape's parameters")
    drive = spec.get("drive") or {}
    if not isinstance(drive, dict):
        raise check.at("drive").error("expected a mapping of parameters to series tracks")
    signature = inspect.signature(get_body(shape))
    for key, where in [(k, "params") for k in params] + [(k, "drive") for k in drive]:
        if key not in signature.parameters:
            raise check.at(where, key).error(
                f"shape {shape!r} has no parameter {key!r} (parameters: "
                f"{', '.join(signature.parameters)})")
    both = sorted(set(params) & set(drive))
    if both:
        raise check.at("drive", both[0]).error("is also in params: a parameter is fixed or driven")
    for key, track in drive.items():
        if not isinstance(track, dict) or "series" not in track:
            raise check.at("drive", key).error("expected a series track {series: NAME, column: ...}")
        try:
            SeriesTrack.parse(track, key)
        except ValueError as exc:
            raise check.at("drive", key).wrap(exc) from None
    series_spec = spec.get("series") or {}
    if not isinstance(series_spec, dict):
        raise check.at("series").error("expected a mapping of series names to files")
    series = {k: _series(k, v, check.at("series", k), folder) for k, v in series_spec.items()}
    return Body(name, None, series=series, virtual=True, shape=shape, params=dict(params),
                attach=_attach(spec.get("attach"), check.at("attach")),
                drive={k: dict(v) for k, v in drive.items()})


def _attach(spec, check: Checker) -> Attach:
    if spec is None:
        return Attach(point=(0.0, 0.0, 0.0))
    spec = check.mapping(spec, ATTACH_KEYS)
    if ("body" in spec) == ("point" in spec):
        raise check.error("give body (with station) or point")
    if "station" in spec and "body" not in spec:
        raise check.at("station").error("a station is along a body: give body")
    offset = check.at("offset").numbers(spec.get("offset", (0, 0, 0)), 3)
    if "point" in spec:
        return Attach(point=check.at("point").numbers(spec["point"], 3), offset=offset)
    station = None if "station" not in spec else check.at("station").number(spec["station"])
    return Attach(body=check.at("body").string(spec["body"]), station=station, offset=offset)


def _check_attach(attach: Attach, bodies: dict, check: Checker) -> None:
    host = bodies.get(attach.body)
    if host is None:
        from flowreel.scene.errors import unknown_key_message
        raise check.at("body").error(unknown_key_message(attach.body, list(bodies))
                                     .replace("unknown key", "no body"))
    if host.virtual:
        raise check.at("body").error(f"{attach.body!r} is virtual; attach to a body with a surface")
    if attach.station is not None and host.axis is None:
        raise check.at("station").error(f"{attach.body!r} has no axis; declare one, or leave "
                                        "the station out to attach at its centre")


def _body(name: str, spec, check: Checker, folder: Path | None) -> Body:
    spec = check.mapping(spec, BODY_KEYS)
    zone = check.at("zone").string(spec.get("zone", name))
    axis = spec.get("axis")
    if axis is not None:
        axis = check.at("axis").choice(axis, AXES)
    diameter = spec.get("diameter")
    if diameter is not None:
        if axis is None:
            raise check.at("diameter").error("a diameter is for a beam body: give the body an "
                                             "'axis' (its span direction), or leave it out")
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
    spec = check.mapping(spec, END_KEYS + SUPPORTS[kind], required=("at",) + REQUIRED.get(kind, ()))
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
