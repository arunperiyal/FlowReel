# Layers without flow data: `outline`, `glyphs`, `markers3d`, `geometry`

Code: `flowreel.scene.marker_layers`. Entries of a shot's `layers:` list
(`docs/shots.md`). *Track* options take a number or keys (`docs/tracks.md`). Colours are
hex strings; lengths and positions are in the source's unit; line widths in pixels. None
of these needs the flow, except `glyphs` with `direction: velocity`; a shot made only of
them (such as one on a `geometry` source) loads no flow.

## Boxes: `bounds` and `in`

A box is `domain` (the source's bounds), `crop` (the shot's crop; the domain when the shot
has none) or numbers `{x: [lo, hi], y: [lo, hi], z: [lo, hi]}` with `lo < hi`.

## `outline`

The twelve edges of a box.

| Key | Type | Default | Example |
|---|---|---|---|
| `bounds` | a box | `domain` | `crop` |
| `colour` | track, colour | `#ffffff` | `"#8899aa"` |
| `width` | track, pixels | `1` | `2` |
| `opacity` | track | `1` | `{from: 0, to: 1, frames: [0, 24]}` |

## `glyphs`

Arrows on a face of a box, or at points.

| Key | Type | Default | Example |
|---|---|---|---|
| `where` | see below, required | | `{face: z-, grid: [8, 4]}` |
| `direction` | track, vector, or `velocity` | `[1, 0, 0]` | `[0, 1, 0]` |
| `size` | track, arrow length | `1` | `0.5` |
| `colour` | track, colour | `#ffffff` | `"#f25c05"` |
| `opacity` | track | `1` | `0.8` |

`where` is either `{face: F, grid: [n, m], in: box}` or `{points: [[x, y, z], ...]}`.
`F` is `x-`, `x+`, `y-`, `y+`, `z-` or `z+`: the face of the box `in` (default `domain`).
The `n x m` arrows sit at the centres of the grid cells; the grid runs along the face's
other two axes in x, y, z order (for `z-`, `n` along x and `m` along y). `direction:
velocity` points each arrow along the local flow, sampled at its position (needs the flow;
arrows where the flow is zero are left out). Arrows have the same length, `size`;
the direction is the information.

## `markers3d`

One solid marker at a position; use one layer per marker.

| Key | Type | Default | Example |
|---|---|---|---|
| `shape` | `arrow3d`, `block`, `sphere`; required | | `sphere` |
| `at` | track, vector; required | | `{from: [0, 1, 0], to: [6, 1, 0], frames: [0, 24]}` |
| `colour`, `opacity` | tracks | `#ffffff`, `1` | |
| `direction` | track, vector (`arrow3d`) | `[1, 0, 0]` | `[0, 0, 1]` |
| `length` | track (`arrow3d`) | `1` | `2` |
| `size` | track, vector of edge lengths (`block`) | `[1, 1, 1]` | `[0.3, 0.3, 0.3]` |
| `radius` | track (`sphere`) | `0.5` | `0.15` |

`at` is the arrow's tail, or the centre of a block or sphere. The length of `direction`
does not matter; a zero `direction` is an error.

## `geometry`

A body built from a registered body function (`docs/sources.md`), with its parameters as
tracks: the groove depth, the carved length, the radius.

| Key | Type | Default | Example |
|---|---|---|---|
| `body` | registered body name; required | | `grooved_cylinder` |
| `params` | mapping of the body's parameters to values or tracks | the body's defaults | `{span: 6, cut_front: {from: 0, to: 4, frames: [0, 60]}}` |
| `colour`, `opacity`, `specular` | tracks | `#c8ccd0`, `1`, `0.4` | |
| `colour_by` | a point array of the surface | none | `fresh` |
| `range`, `colormap` | for `colour_by` | `[0, 1]`, `fire_ice` | `[0, 1]`, `viridis` |

Unknown parameters are errors when the shot is read, with the nearest name suggested.
The surface is rebuilt each frame from the tracks' values; the renderer will reuse it
while they do not change.

## Example

`examples/marker_layers/` draws all four on generated data, with no files to download:
`python examples/marker_layers/run.py` writes three frames.
