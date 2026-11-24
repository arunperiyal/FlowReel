# Flow layers: `iso`, `slice`, `body`

Code: `flowreel.scene.flow_layers`. Each layer is one entry of a shot's `layers:` list
(`docs/guide/shots/shots.md`). Options marked *track* take a number or keys (`docs/guide/shots/tracks.md`).
Colours are hex strings. `colormap` is `fire_ice` (black at the middle, so weak flow fades
into a black background; blue-white for negative, orange-white for positive) or any
matplotlib name. Lengths are in the source's unit. Derived fields (`lambda2`, `Q`,
`vorticity_x`, `speed`, ...) are described in `docs/guide/projects/fields.md`.

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
| `range` | vector track, `[low, high]` | `[-1, 1]` | `{from: [-200, 200], to: [-20, 20], frames: [0, 48]}` |
| `colormap` | as `iso` | `fire_ice` | `viridis` |
| `opacity` | track | `1` | `{from: 0, to: 1, frames: [0, 2.4]}` |
| `fade_weak` | `[low, high]` | none | `[0.05, 0.5]` |
| `near_wall` | `[low, high]`, length | none | `[0.03, 0.1]` |
| `mask_body` | body name | all bodies | `riser` |

`range` may sweep: the plane is coloured afresh in every frame, so narrowing the range
over a frozen step brings out weaker flow. `iso` and `body` keep a fixed range.

`fade_weak`: opacity rises smoothly from 0 where `|field| <= low` to 1 where
`|field| >= high`. `near_wall`: it rises the same way with the distance from the body, so
the section does not paint over the wall. Both multiply with `opacity`.

## `contour`

Lines of `field` at chosen values, on a plane through the flow: isobars over a slice of
vorticity, say, or lines of the same speed.

| Key | Type | Default | Example |
|---|---|---|---|
| `normal` | `x`, `y`, `z`, required | | `z` |
| `position` | track, length, required | | `0.0` |
| `field` | field name, required | | `pressure` |
| `levels` | a list of values, or a count | `11` | `[-400, -200, 0, 200, 400]` |
| `range` | vector track, `[low, high]` | `[-1, 1]` | `[-1100, 1100]` |
| `colour` | track, colour | `#ffffff` | `"#000000"` |
| `colormap` | as `iso`; colours each line by its value | none: `colour` | `fire_ice` |
| `width` | track, pixels | `2` | `1.5` |
| `opacity` | track | `1` | `0.6` |

`levels: 11` draws 11 lines spread evenly from `range`'s low end to its high end, both
included; a list draws one line at each value. `range` also spans the colour map when
`colormap` is given. It may sweep, and a count of levels sweeps with it, the lines
moving as the range narrows; listed levels stay put. A level that the plane does not
cross draws nothing.

Draw it after a `slice` on the same plane, so the lines lie over the colours:

```yaml
layers:
  - {type: slice, normal: z, position: 0, field: vorticity_z, range: [-60, 60]}
  - {type: contour, normal: z, position: 0, field: pressure, levels: 15, range: [-700, 700],
     colour: '#ffffff', width: 1.5, opacity: 0.7}
```

## `streamlines`

Lines along the velocity, traced both ways from seed points: the path the flow takes
past a body, or round a vortex.

| Key | Type | Default | Example |
|---|---|---|---|
| `seeds` | one of `line`, `plane`, `round` (below), required | | `{line: {from: [-2, -1, 0], to: [-2, 1, 0], count: 20}}` |
| `length` | length | the flow's diagonal | `8.0` |
| `style` | `lines` or `tubes` | `lines` | `tubes` |
| `width` | track, pixels; with `lines` | `2` | `1.5` |
| `radius` | length; with `tubes` | 0.2 % of the diagonal | `0.01` |
| `colour` | track, colour | `#ffffff` | `"#e8b04a"` |
| `field` | field name; colours the lines by it | none: `colour` | `speed` |
| `range` | vector track, `[low, high]`; with `field` | `[-1, 1]` | `[0, 1.2]` |
| `colormap` | as `iso`; with `field` | `fire_ice` | `viridis` |
| `opacity` | track | `1` | `0.8` |
| `relative` | `false`, `true` or `{body, station}` | `false` | `true` |

The seeds:

| Seeds | Keys | Example |
|---|---|---|
| `line` | `from`, `to` (points), `count` (ends included) | `{from: [-2, -1, 0], to: [-2, 1, 0], count: 20}` |
| `plane` | `normal` (`x`, `y` or `z`), `position`, `lo` and `hi` (corners on the plane, the two other axes in x, y, z order), `counts` (`[n, m]`) | `{normal: z, position: 0, lo: [-2, -1], hi: [-2, 1], counts: [1, 20]}` |
| `round` | `body` (left out when there is one), `station` along its axis, `radius` (times its diameter, default `0.75`), `count` | `{body: cylinder, station: 0, radius: 0.6, count: 24}` |

Each line runs `length` each way from its seed, or stops where it leaves the flow or the
flow stops. `relative: true` traces the lines in the velocity relative to the body, so a
moving body's wake is drawn as the body sees it, as the [section panel](panels.md)
draws its streamlines. The body's speed comes from its centre at the saved steps either
side; `true` takes the body and station of `round` seeds, and with other seeds give
`{body: NAME, station: S}`.

## `body`

| Key | Type | Default | Example |
|---|---|---|---|
| `body` | name, list of names, or `all` | `all` | `[riser, mast]` |
| `colour` | track, colour | `#c8ccd0` | `"#c8ccd0"` |
| `opacity` | track | `1` | `0.8` |
| `style` | `solid` or `ghost` | `solid`; `ghost` when every body drawn is virtual | `ghost` |
| `edge_width` | track, pixels: a ghost's outline | `1.5` | `2` |
| `specular` | track | `0.4` | `0.2` |
| `field` | name | none | `speed` |
| `range`, `colormap` | as `iso`, for `field` | `[-1, 1]`, `fire_ice` | `[0, 1]` |
| `zero_contour` | track, boolean | `false` | `true` |
| `zero_colour` | track, colour | `#ffffff` | `"#ffffff"` |
| `zero_width` | track, pixels | `2` | `3` |
| `amplify` | track: the displacement from rest drawn this many times larger | `1` | `50` |
| `rest_step` | step whose shape is the rest shape | the first saved step | `5000` |

`ghost` draws the body at a third of its opacity and without highlights, so the flow shows
through it, with an outline `edge_width` pixels wide in its colour. Virtual bodies
([bodies](../projects/bodies.md#virtual-bodies)) are ghosts unless `style` is given, and have no
wall: `field` on one is an error. With `field`, the surface takes the colour of that field: an array already on
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
`tests/data/reveal/reveal.yml` (`docs/guide/reveal.md`).
