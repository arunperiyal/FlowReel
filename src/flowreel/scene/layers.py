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

from flowreel.scene.backend import plain_vtk_filters

plain_vtk_filters()           # every layer cuts with VTK's own filters (see there)

_MISSING = object()


@dataclass(frozen=True)
class Option:
    """One option of a layer type.

    ``kind`` is a track kind (``number``, ``vector``, ``colour``, ``boolean``, ``choice``)
    or ``None`` to infer it. ``default`` is used when the key is absent; ``required``
    options have none. ``track=False`` keeps the raw YAML value. ``choices`` limits a
    ``choice``. ``pixels`` marks a size in pixels (a line width), which a draft render
    scales with the picture. ``doc`` is the line the reference and ``shot template`` print;
    ``example`` is the value ``shot template`` writes for a required option.
    """

    name: str
    kind: str | None = None
    default: Any = None
    required: bool = False
    track: bool = True
    choices: tuple = ()
    pixels: bool = False
    doc: str = ""
    example: Any = None


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

    ``crop`` is the shot's crop box (``None``: whole domain), ``source`` the source and
    ``step`` the step. ``flow`` is the volume of the frame's step (``UnstructuredGrid``):
    given, or read from the source (fields ``FLOW_FIELDS``, inside the crop) the first
    time a layer asks for it, so a frame whose layers never read it never loads it.
    ``body(name)`` gives a wall surface (``None`` for all of them), read once per frame.
    ``need(*fields)`` adds derived fields to ``flow`` the first time they are asked for.
    ``cached(key, build)`` returns a surface from the renderer's cache, or builds it.
    ``fields`` are the arrays read from the source (default ``FLOW_FIELDS``; a scene
    gives :func:`flow_fields`, with ``p`` when a layer's field needs the pressure).
    ``reference`` holds the project's reference values (``flowreel.yml``), which derived
    fields take as parameters (``rho``, ``u_inf``).
    """

    FLOW_FIELDS = ("U", "V", "W")

    def __init__(self, source, step: int, flow=None, crop=None, cache=None, fields=None,
                 reference=None):
        self.source, self.step, self.crop, self.cache = source, step, crop, cache
        self.fields = tuple(fields or self.FLOW_FIELDS)
        self.reference = dict(reference or {})
        self._flow = flow
        self._bodies: dict = {}

    @property
    def flow(self):
        """The flow volume of this step, read on first use."""
        if self._flow is None:
            self._flow = self.source.flow(self.step, list(self.fields), self.crop)
        return self._flow

    @property
    def flow_loaded(self) -> bool:
        """True once the flow has been given or read."""
        return self._flow is not None

    def cached(self, key: dict, build: Callable):
        """``build()``, or the mesh stored under ``key`` by the renderer's cache.

        ``key`` lists everything the mesh depends on except the source, step and crop,
        which are added here. Without a cache this is ``build()``.
        """
        if self.cache is None:
            return build()
        from flowreel.scene.keys import file_stamps
        return self.cache.get({**key, "step": self.step,
                               "files": file_stamps(self.source, self.step),
                               "crop": None if self.crop is None else
                               [list(self.crop.lo), list(self.crop.hi)]}, build)

    def body(self, name=None):
        """The wall surface called ``name`` at this step (all bodies when ``None``)."""
        if name not in self._bodies:
            self._bodies[name] = self.source.body(self.step, name)
        return self._bodies[name]

    def need(self, *names: str) -> None:
        """Make sure ``flow`` carries the fields ``names`` (computed from U, V, W, p, with
        the reference values the fields take)."""
        from flowreel import fields
        from flowreel.fields.registry import accepted
        missing = [n for n in names if n not in self.flow.point_data]
        if not missing:
            return
        params = {k: v for k, v in self.reference.items() if k in accepted(missing)}
        for name, value in fields.compute(self.flow, missing, **params).items():
            self.flow.point_data[name] = value


def flow_fields(source, layers) -> tuple[str, ...]:
    """The arrays to read from ``source`` for ``layers``: the velocity always, ``p``
    when a layer's ``field`` or ``colour_by`` needs the pressure and the source has it,
    and any it names that the source provides itself. A name that is neither (an array
    on a body's own surface) is left to its layer. A source without ``fields()`` is
    read for the velocity alone, as every frame was before."""
    from flowreel.fields.registry import available, resolve
    lister = getattr(source, "fields", None)
    provided = set(lister()) if callable(lister) else set(FrameData.FLOW_FIELDS)
    names = [n for layer in layers for key in ("field", "colour_by")
             if isinstance(n := layer.raw.get(key), str)]
    out = list(FrameData.FLOW_FIELDS)
    derived = [n for n in names if n not in provided and n in available()]
    if derived and "pressure" in resolve(derived) and "p" in provided:
        out.append("p")
    out += [n for n in names if n in provided and n not in out]
    return tuple(out)


class Layer:
    """Base class of layer types. Subclasses set ``name`` and ``options`` and override
    :meth:`draw`.

    ``needs_flow`` says whether the layer reads the flow volume; layers that do not
    (outline, markers) let the renderer skip loading it.
    """

    name: str = ""
    options: tuple[Option, ...] = ()
    needs_flow: bool = False
    allow_text: tuple[str, ...] = ()   # tracked options that may also be a plain word

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

    @classmethod
    def check(cls, raw: dict, check: Checker) -> None:
        """Validate (and may rewrite) the untracked options ``raw`` at build time.

        Raise through ``check.at(key).error(...)`` so the message names the key path.
        """

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
        if not opt.track or (opt.kind == "vector" and isinstance(value, str)
                             and opt.name in cls.allow_text):
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
    cls.check(raw, check)
    return cls(tracks, raw)
