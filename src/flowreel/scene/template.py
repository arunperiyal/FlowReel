"""A commented shot file with the defaults, for ``flowreel shot template``.

It is generated from the shot's keys and each layer type's declared options (name,
default, doc), so it cannot drift from the code. Options without a default are written
commented out; required ones get an example value. The result loads as a shot once
``source`` and ``camera`` name real things.
"""
from __future__ import annotations

import yaml

from flowreel.scene import flow_layers as _flow_layers  # noqa: F401  (registers layers)
from flowreel.scene import marker_layers as _marker_layers  # noqa: F401
from flowreel.scene import supports as _supports  # noqa: F401
from flowreel.scene import centreline as _centreline  # noqa: F401
from flowreel.scene import axes as _axes  # noqa: F401
from flowreel.scene.layers import available, layer_type

HEADER = """\
# Shot file written by `flowreel shot template`. Reference: docs/shots.md; layers:
# docs/layers-flow.md and docs/layers-markers.md; tracks: docs/tracks.md.
{name_line}
source: vtk:flow.pvd                  # adapter:location, or {{adapter: vtk, path: ..., body: ...}}
time: {{frozen: 0, frames: 48}}         # or {{steps: [first, last], every: 1}} or {{keys: [[frame, step], ...]}}
camera: {{view: main}}                  # a view of cameras.yml; or {{track: T}}, {{fit: domain, direction_of: V}}
size: [1920, 1080]                    # width, height in pixels
# crop: {{x: [lo, hi], y: [lo, hi], z: [lo, hi]}}   # read only this box of the source
background: black                     # a colour name or '#rrggbb'
antialias: ssaa                       # none, fxaa or ssaa
# lights: raking                      # default, raking or a list; without it, VTK's light kit
# watermark: {{text: 'A. Periyal', corner: lower_right, size: 32, opacity: 0.7}}   # or {{image: FILE, ...}}; drawn into every frame
layers:                               # drawn bottom first
"""

COLUMN = 38


def _value(v) -> str:
    if isinstance(v, tuple):
        v = list(v)
    text = yaml.safe_dump(v, default_flow_style=True, width=1000).strip()
    return text[:-4].strip() if text.endswith("\n...") else text.removesuffix("...").strip()


def _line(text: str, comment: str) -> str:
    # A comment needs a space before '#' in YAML, even when the text is past the column.
    return f"{text.ljust(COLUMN - 1)} # {comment}" if comment else text


def layer_block(name: str) -> str:
    """The YAML of one layer of type ``name``, every option with its default."""
    cls = layer_type(name)
    lines = [f"  - type: {name}"]
    for opt in cls.options:
        notes = []
        if opt.required:
            notes.append("required")
        if opt.track:
            notes.append("track")
        if opt.pixels:
            notes.append("pixels")
        if opt.choices:
            notes.append("one of " + ", ".join(map(str, opt.choices)))
        if opt.doc:
            notes.append(opt.doc)
        comment = "; ".join(notes)
        value = opt.example if opt.required else opt.default
        if value is None:
            lines.append(_line(f"    # {opt.name}: ~", comment))
        else:
            lines.append(_line(f"    {opt.name}: {_value(value)}", comment))
    return "\n".join(lines)


def template(name: str = "my_shot", layers: list[str] | None = None) -> str:
    """The text of a shot file named ``name`` with ``layers`` (layer type names, default
    ``["body"]``). Raises ``ValueError`` for an unknown layer type."""
    layers = layers or ["body"]
    unknown = [n for n in layers if n not in available()]
    if unknown:
        raise ValueError(f"unknown layer type {unknown[0]!r} (one of: {', '.join(available())})")
    name_line = _line(f"name: {name}", f"names the frame folder, frames/{name}/")
    return HEADER.format(name_line=name_line) + "\n".join(layer_block(n) for n in layers) + "\n"
