"""Layer interface and registry (plan Section 7.2).

A layer type declares its options; a shot file instantiates it. Each frame the renderer
calls :meth:`Layer.draw` with the frame's data and the value of every option at that
frame, and the layer adds actors to the plotter. Layer types register under a name
(``iso``, ``slice``, ...) so that Phase 2's other branches add theirs without touching
the shot reader.

Options are tracks by default: ``opacity: 1`` and ``opacity: {from: 0, to: 1, frames:
[0, 24]}`` are both accepted. An option with ``track=False`` is read as it is (a field
name, a list of body names).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from flowreel import tracks as tracks_mod
from flowreel.scene.errors import Checker

_MISSING = object()


@dataclass(frozen=True)
class Option:
    """One option of a layer type.

    ``kind`` is a track kind (``number``, ``vector``, ``colour``, ``boolean``, ``choice``)
    or ``None`` to infer it. ``default`` is used when the key is absent; ``required``
    options have none. ``track=False`` keeps the raw YAML value. ``choices`` limits a
    ``choice``. ``doc`` is the line the reference and ``shot template`` print.
    """

    name: str
    kind: str | None = None
    default: Any = None
    required: bool = False
    track: bool = True
    choices: tuple = ()
    doc: str = ""


@dataclass
class Frame:
    """What a layer sees for one frame.

    ``index`` is the frame number, ``step`` the simulation step shown, ``time`` its
    physical time, ``data`` the loaded flow and bodies (filled by the renderer), and
    ``values`` the options at this frame: one dict per layer in a frame plan (in the
    order of the shot's layers), the layer's own dict when passed to :meth:`Layer.draw`.
    """

    index: int
    step: int
    time: float
    data: Any = None
    values: Any = field(default_factory=dict)


class FrameData:
    """The data of one frame, as layers read it.

    ``flow`` is the volume of the frame's step (``UnstructuredGrid``; ``None`` when no
    layer needs it), ``source`` the source and ``step`` the step. ``body(name)`` gives a
    wall surface (``None`` for all of them), read once per frame. ``need(*fields)`` adds
    derived fields to ``flow`` the first time they are asked for.
    """

    def __init__(self, source, step: int, flow=None):
        self.source, self.step, self.flow = source, step, flow
        self._bodies: dict = {}

    def body(self, name=None):
        """The wall surface called ``name`` at this step (all bodies when ``None``)."""
        if name not in self._bodies:
            self._bodies[name] = self.source.body(self.step, name)
        return self._bodies[name]

    def need(self, *names: str) -> None:
        """Make sure ``flow`` carries the fields ``names`` (computed from U, V, W, p)."""
        from flowreel import fields
        missing = [n for n in names if n not in self.flow.point_data]
        for name, value in fields.compute(self.flow, missing).items():
            self.flow.point_data[name] = value


class Layer:
    """Base class of layer types. Subclasses set ``name`` and ``options`` and override
    :meth:`draw`.

    ``needs_flow`` says whether the layer reads the flow volume; layers that do not
    (outline, markers) let the renderer skip loading it.
    """

    name: str = ""
    options: tuple[Option, ...] = ()
    needs_flow: bool = False

    def __init__(self, tracks: dict, raw: dict):
        self.tracks = tracks   # option name -> Track (tracked options)
        self.raw = raw         # option name -> value (untracked options)

    def values(self, frame: float) -> dict:
        """Every option's value at ``frame``."""
        out = dict(self.raw)
        out.update({k: t.at(frame) for k, t in self.tracks.items()})
        return out

    def key_fields(self, frame: float) -> dict:
        """What decides whether the frame's image changed (Section 11): the values."""
        return self.values(frame)

    def draw(self, plotter, frame: Frame) -> None:
        """Add this layer's actors to ``plotter`` for ``frame``."""
        raise NotImplementedError(f"layer {self.name!r} cannot draw yet")


_layers: dict[str, type[Layer]] = {}


def register(cls: type[Layer]) -> type[Layer]:
    """Register a layer class under ``cls.name`` (usable as a decorator)."""
    if not cls.name:
        raise ValueError("a layer class needs a name")
    if cls.name in _layers:
        raise ValueError(f"layer type {cls.name!r} is already registered")
    _layers[cls.name] = cls
    return cls


def available() -> list[str]:
    """Names of the registered layer types."""
    return sorted(_layers)


def layer_type(name: str) -> type[Layer]:
    """The class registered as ``name``."""
    return _layers[name]


def build(spec, check: Checker) -> Layer:
    """Build a layer from its YAML mapping: ``{type: iso, field: Q, level: -0.1, ...}``.

    ``check`` points at the layer (for error paths). Unknown types and options suggest
    the nearest valid name.
    """
    if not isinstance(spec, dict):
        raise check.error("a layer is a mapping with a 'type' key")
    if "type" not in spec:
        raise check.error("missing key 'type'")
    kind = check.at("type").choice(spec["type"], available())
    cls = _layers[kind]
    names = ("type",) + tuple(o.name for o in cls.options)
    check.mapping(spec, names)
    tracks, raw = {}, {}
    for opt in cls.options:
        where = check.at(opt.name)
        if opt.name not in spec:
            if opt.required:
                raise check.error(f"missing key {opt.name!r}")
            value = opt.default
            if value is None:
                continue
        else:
            value = spec[opt.name]
        if not opt.track:
            raw[opt.name] = value
            continue
        try:
            track = tracks_mod.parse(value, kind=opt.kind, name=opt.name)
        except ValueError as exc:
            raise where.wrap(exc) from None
        if opt.choices:
            for v in track.values:
                where.choice(v, opt.choices)
        tracks[opt.name] = track
    return cls(tracks, raw)
