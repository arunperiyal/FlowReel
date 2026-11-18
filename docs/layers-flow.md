# Flow layers: `iso`, `slice`, `body`

Code: `flowreel.scene.flow_layers`. Each layer is one entry of a shot's `layers:` list
(`docs/shots.md`). Options marked *track* take a number or keys (`docs/tracks.md`).
Colours are hex strings. `colormap` is `fire_ice` (black at the middle, so weak flow fades
into a black background; blue-white for negative, orange-white for positive) or any
matplotlib name. Lengths are in the source's unit. Derived fields (`lambda2`, `Q`,
`vorticity_x`, `speed`, ...) are described in `docs/fields.md`.

## `iso`

An isosurface of `field` at `level`.

| Key | Type | Default | Example |
|---|---|---|---|
| `field` | field name, required | | `lambda2` |
| `level` | track, required | | `{keys: [[0, -0.1], [120, -1.0]], ease: out}` |
| `colour_by` | field name | none (solid `colour`) | `vorticity_x` |
| `range` | `[low, high]`, the values at the ends of `colormap` | `[-1, 1]` | `[-2.5, 2.5]` |
| `colormap` | name | `fire_ice` | `viridis` |
| `colour` | track, colour | `#c8ccd0` | `"#6f8796"` |
| `opacity` | track | `1` | `0.6` |
| `wall_gap` | track, length | `0` | `0.4` |
| `gap_body` | body name | all bodies | `riser` |
| `clip_axis` | `x`, `y`, `z` | none | `x` |
| `clip_position` | track, length | `0` | `{from: 4.1, to: 6.0, frames: [0, 24]}` |
| `clip_keep` | `below` or `above` the plane | `below` | `above` |
| `clip_active` | track, boolean | `true` | `{keys: [[0, false], [0.01, true]]}` |
| `grow_axis` | `x`, `y`, `z` | none | `z` |
| `grow` | track, 0 to 1 | `1` | `{from: 0, to: 1, frames: [0, 48]}` |
| `grey` | track, 0 to 1 | `0` | `{from: 0, to: 1, frames: [10, 24]}` |
| `grey_colour` | track, colour | `#6f8796` | `"#808080"` |

- **`wall_gap`** hides surface nearer than the gap to the body: it removes the sheath of
  high rotation wrapped round a wall, which is not part of the wake.
- **Clip** keeps one side of the plane `axis = clip_position`. `clip_active: false` shows
  the surface whole.
- **`grow`** shows the part of the surface up to that fraction of the surface's own
  extent along `grow_axis` (measured before any clip), so a wake appears to travel
  downstream from its upstream end and is whole at 1, wherever the flow box ends. This
  is the prototype's wake growth in the domain shot.
- **`grey`** blends the colours to `grey_colour` in display (sRGB) values, as the
  prototype does.

## `slice`

A plane through the flow, coloured by `field`.

| Key | Type | Default | Example |
|---|---|---|---|
| `normal` | `x`, `y`, `z`, required | | `x` |
| `position` | track, length, required | | `{from: 0.02, to: 6.0, frames: [48, 72]}` |
| `field` | field name, required | | `vorticity_x` |
| `range`, `colormap` | as `iso` | `[-1, 1]`, `fire_ice` | `[-2.5, 2.5]` |
| `opacity` | track | `1` | `{from: 0, to: 1, frames: [0, 2.4]}` |
| `fade_weak` | `[low, high]` | none | `[0.05, 0.5]` |
| `near_wall` | `[low, high]`, length | none | `[0.03, 0.1]` |
| `mask_body` | body name | all bodies | `riser` |

`fade_weak`: opacity rises smoothly from 0 where `|field| <= low` to 1 where
`|field| >= high`. `near_wall`: it rises the same way with the distance from the body, so
the section does not paint over the wall. Both multiply with `opacity`.

## `body`

| Key | Type | Default | Example |
|---|---|---|---|
| `body` | name, list of names, or `all` | `all` | `[riser, mast]` |
| `colour` | track, colour | `#c8ccd0` | `"#c8ccd0"` |
| `opacity` | track | `1` | `0.8` |
| `style` | `solid` or `ghost` | `solid` | `ghost` |
| `specular` | track | `0.4` | `0.2` |
| `field` | name | none | `speed` |
| `range`, `colormap` | as `iso`, for `field` | `[-1, 1]`, `fire_ice` | `[0, 1]` |
| `zero_contour` | track, boolean | `false` | `true` |
| `zero_colour` | track, colour | `#ffffff` | `"#ffffff"` |
| `zero_width` | track, pixels | `2` | `3` |
| `amplify` | track: the displacement from rest drawn this many times larger | `1` | `50` |
| `rest_step` | step whose shape is the rest shape | the first saved step | `5000` |

`ghost` draws the body at a third of its opacity and without highlights, so the flow shows
through it. With `field`, the surface takes the colour of that field: an array already on
the body, or a derived field computed on the flow and sampled onto the surface (the flow
is then loaded). `zero_contour` draws the line where `field` is 0; with a wall shear
component that line is where the flow separates.

`amplify` moves every point of the surface from its place at `rest_step` by `amplify`
times its displacement, so a vibration of a hundredth of a diameter can be seen. The
surface must have the same points at every step (as a solver's deformed mesh does). It
is refused in a shot with flow layers (`iso`, `slice`, `glyphs` of the velocity): a body
moved 50 times further than it went no longer fits the flow around it. For a long body,
the [`centreline`](layers-markers.md#centreline) may amplify in any shot.

## Example

`examples/flow_layers/` writes a small generated vortex case and draws a shot with the
three layers: `python examples/flow_layers/run.py`. The full reveal shot is
`tests/data/reveal/reveal.yml` (`docs/reveal.md`).
