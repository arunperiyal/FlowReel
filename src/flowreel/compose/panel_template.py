"""Commented panel files, one per type (``flowreel panel template``).

Each template is a working example of its type, written for a project of tags (bodies
named ``tag.body``, sources by tag), followed by the type's other keys, commented out.
The keys and their meaning are in the guide (``docs/guide/shots/panels.md``).
"""
from __future__ import annotations

HEAD = """# A {type} panel, written by `flowreel panel template --type {type}`. Reference:
# docs/guide/shots/panels.md#{anchor}. A panel is drawn with matplotlib; in a film of
# scenes, a panel box draws it at the box's size (`panel draw` draws its own frames).
type: {type}
size: {size}                         # width, height in pixels (a panel box uses its own)
times: {times}
# style: styles/film.yml               # fonts and colours, shared with the film
"""

BODIES = {
    "series": ("series", "[640, 1080]", "{shot: ../shots/wake.yml}   # the frame times of a shot; or a list", """\
x: {label: '$tU/D$'}
rows:                                # one plot each, sharing the time axis
  - label: 'Mid-span $y/D$'
    lines:
      - {body: smooth.cyl, series: displacement, column: dy, label: smooth}
      - {body: helical.cyl, series: displacement, column: dy, label: helical}
  - label: '$C_L$'
    range: [-1.5, 1.5]
    lines:
      - {body: smooth.cyl, series: force, column: fy}
# legend: true
# margins: {left: 0.2, right: 0.95, top: 0.93, bottom: 0.08, space: 0.18}
"""),
    "phase": ("phase", "[400, 400]", "{shot: ../shots/wake.yml}", """\
x: {body: smooth.cyl, series: displacement, column: dy, label: '$y/D$'}
y: {body: smooth.cyl, series: force, column: fy, label: '$C_L$'}
colour: '#d8707a'
# margins: {left: 0.2, right: 0.95, top: 0.93, bottom: 0.15}
"""),
    "map": ("map", "[1920, 1080]", "{shot: ../shots/wake.yml}", """\
x: {label: '$tU/D$'}
y: {label: 'Span $x/D$'}
rows:                                # one map each: a history at many points
  - {body: smooth.cyl, series: sections, column: cy, title: smooth}
  - {body: helical.cyl, series: sections, column: cy, title: helical}
colormap: fire_ice
range: [-1.5, 1.5]
colorbar: {label: 'Sectional $C_L$'}
# margins: {...}
# title_size: 28
"""),
    "locator": ("locator", "[1920, 200]", "{shot: ../shots/travel.yml}", """\
body: smooth.cyl
shape: {series: displacement, column: dy, amplify: 100}
windows: [{shot: ../shots/travel.yml, label: window}]
x: {label: 'Span $x/D$'}
# supports: true
# y: {...}
# colour: '#c8ccd0'
# margins: {...}
"""),
    "section": ("section", "[1920, 1080]", "{shot: ../shots/travel.yml}", """\
source: smooth                       # a tag; or the shot's in times: {shot: ...}
body: cyl
station: 6.0
field: vorticity_x
range: [-30, 30]
half: 1.4
inset: {offset: [0.2, 0.45], half: 0.3}
# streamlines: true
# params: {}                         # a field's parameters; the tag's units by default
# colormap: fire_ice
# levels: 21
# view: [0.02, 0.02, 0.96, 0.96]
# axes: true
# depth: 0.1
# centre: [0, 0]
# body_colour: '#c8ccd0'
"""),
    "cuts": ("cuts", "[1920, 540]", "{shot: ../shots/travel.yml}", """\
source: smooth
body: cyl
stations: [3, 6, 9]
field: vorticity_x
range: [-2.5, 2.5]
centre: [3.5, 0]
half: [5, 4.2]
label: 'x = {station:g} D'
# gap: 0.02
"""),
    "strip": ("strip", "[1920, 540]", "{shot: ../shots/travel.yml}", """\
source: smooth
body: cyl
side: y
field: skin_friction
component: z
range: [-0.03, 0.03]
# zero: true                         # the line where the field is zero
# span: [0, 12]
# margin: 0.1
# aspect: equal
"""),
}

TYPES = tuple(BODIES)


def template(kind: str = "series") -> str:
    """The text of a panel file of type ``kind`` (one of :data:`TYPES`)."""
    if kind not in BODIES:
        raise ValueError(f"unknown panel type {kind!r} (one of: {', '.join(TYPES)})")
    anchor, size, times, body = BODIES[kind]
    return HEAD.format(type=kind, anchor=anchor, size=size, times=times) + body
