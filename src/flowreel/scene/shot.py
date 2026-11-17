"""The shot file (plan Section 7.1): one YAML file describes one shot.

.. code-block:: yaml

    name: bare_reveal
    source: flexflow:bare/BR0SG0U1P0
    time: {steps: [5000, 5600], every: 5}
    camera: {view: main}
    size: [1920, 1080]
    crop: {x: [-1, 13], y: [-6, 6], z: [-2, 25]}
    background: black
    antialias: ssaa
    layers: [...]

:func:`load` reads a file, :func:`from_dict` an already parsed mapping. Both return a
:class:`Shot` or raise :class:`~flowreel.scene.errors.ConfigError`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from flowreel.box import Box
from flowreel.scene.errors import Checker, ConfigError

KEYS = ("name", "source", "time", "camera", "size", "crop", "background", "antialias",
        "lights", "layers")
REQUIRED = ("name", "source", "time", "layers")
ANTIALIAS = ("none", "fxaa", "ssaa")
DEFAULT_SIZE = (1920, 1080)


@dataclass
class Shot:
    """A parsed shot file.

    ``source`` is ``(adapter, location)``, from ``adapter:location``; the mapping form
    ``{adapter: vtk, path: ..., body: ...}`` also fills ``source_options``, the other
    keys as written, passed to the adapter (:func:`flowreel.scene.rendering.open_source`
    resolves paths). ``time`` and
    ``camera`` hold the mapping as written; the frame plan and the camera code read
    them. ``size`` is ``(width, height)`` in pixels. ``crop`` is the box read from the
    source, or ``None`` for the whole domain. ``layers`` are built layer objects, bottom
    first. ``lights`` is a tuple of :class:`~flowreel.scene.lights.Light`, or ``None``
    for VTK's own light kit. Lengths are in the source's unit.
    """

    name: str
    source: tuple[str, str]
    time: dict
    layers: list
    camera: dict = field(default_factory=dict)
    size: tuple[int, int] = DEFAULT_SIZE
    crop: Box | None = None
    background: str | list = "black"
    antialias: str = "ssaa"
    lights: tuple | None = None
    source_options: dict = field(default_factory=dict)
    file: str | None = None


def load(path: str | Path) -> Shot:
    """Read the shot file at ``path``. Errors name the file."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark else "syntax"
        raise ConfigError(f"{where}: {getattr(exc, 'problem', None) or exc}", path) from None
    return from_dict(data, file=str(path))


def from_dict(data, file: str | None = None) -> Shot:
    """Check ``data`` (a parsed YAML mapping) and build the :class:`Shot`."""
    from flowreel.scene import layers as layer_mod
    from flowreel.scene import centreline, flow_layers, marker_layers, supports  # noqa: F401  (register the layer types)
    check = Checker(file)
    data = check.mapping(data, KEYS, REQUIRED)
    name = check.at("name").string(data["name"])
    source, source_options = _source(data["source"], check.at("source"))
    time = check.at("time").mapping(data["time"], _TIME_KEYS)
    camera = check.at("camera").mapping(data.get("camera", {}), _CAMERA_KEYS)
    size = _size(data.get("size", DEFAULT_SIZE), check.at("size"))
    crop = _crop(data.get("crop"), check.at("crop"))
    background = data.get("background", "black")
    antialias = check.at("antialias").choice(data.get("antialias", "ssaa"), ANTIALIAS)
    lights = None
    if data.get("lights") is not None:
        from flowreel.scene.lights import parse_lights
        lights = parse_lights(data["lights"], check.at("lights"))
    items = check.at("layers").sequence(data["layers"], minimum=1)
    layers = [layer_mod.build(spec, check.at("layers", i)) for i, spec in enumerate(items)]
    _check_amplify(items, layers, check)
    return Shot(name=name, source=source, time=time, layers=layers, camera=camera,
                size=size, crop=crop, background=background, antialias=antialias,
                lights=lights, source_options=source_options, file=file)


def _check_amplify(items, layers, check: Checker) -> None:
    """``amplify`` on a ``body`` layer is refused in a shot that draws the flow: a body
    moved 50 times further than it went no longer matches the flow around it (plan
    Section 5.6). The ``centreline`` layer may amplify anywhere: it is a diagram."""
    flow = [i for i, layer in enumerate(layers) if layer.needs_flow]
    if not flow:
        return
    for i, (spec, layer) in enumerate(zip(items, layers)):
        if layer.name == "body" and "amplify" in spec:
            raise check.at("layers", i, "amplify").error(
                f"a body drawn amplified would not match the flow of layers[{flow[0]}] "
                f"({layers[flow[0]].name}); amplify in a shot without flow layers, or use "
                "a centreline layer")


# Keys of the sub-mappings. Time is read by scene.plan, camera by scene.camera.
_TIME_KEYS = ("steps", "every", "frozen", "frames", "keys", "ease")
_CAMERA_KEYS = ("view", "track", "fit", "direction_of", "margin", "follow", "station",
                "axis", "motion")


def _source(value, check: Checker) -> tuple[tuple[str, str], dict]:
    if isinstance(value, dict):
        if "adapter" not in value:
            raise check.error("missing key 'adapter' (for example {adapter: vtk, path: flow.pvd})")
        adapter = check.at("adapter").string(value["adapter"])
        options = {k: v for k, v in value.items() if k != "adapter"}
        for k in options:
            if not isinstance(k, str):
                raise check.error(f"option names are words, got {k!r}")
        location = options.get("path", options.get("body", ""))
        return (adapter, str(location)), options
    text = check.string(value)
    adapter, sep, location = text.partition(":")
    if not sep or not adapter or not location:
        raise check.error(f"expected 'adapter:location' (for example flexflow:bare/BR0SG0U1P0) "
                          f"or {{adapter: ..., path: ...}}, got {text!r}")
    return (adapter, location), {}


def _size(value, check: Checker) -> tuple[int, int]:
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected [width, height], got {len(items)} entries")
    return tuple(check.at(i).integer(v, minimum=1) for i, v in enumerate(items))


def _crop(value, check: Checker) -> Box | None:
    if value is None:
        return None
    crop = check.mapping(value, ("x", "y", "z"), required=("x", "y", "z"))
    ranges = [check.at(a).numbers(crop[a], 2) for a in "xyz"]
    for axis, (lo, hi) in zip("xyz", ranges):
        if lo >= hi:
            raise check.at(axis).error(f"expected [low, high] with low < high, got [{lo}, {hi}]")
    return Box(lo=tuple(r[0] for r in ranges), hi=tuple(r[1] for r in ranges))
