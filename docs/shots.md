# Shot files

A **shot** is one continuous piece of film: one source, one camera, a time, and a stack of
layers. It is one YAML file. Everything a shot can vary over time is a
[track](tracks.md), so the file holds the whole shot and no code does.

```yaml
name: bare_reveal
source: plt:bare/BR0SG0U1P0
time: {steps: [5000, 5600], every: 5}
camera: {view: main}
size: [1920, 1080]
crop: {x: [-1, 13], y: [-6, 6], z: [-2, 25]}
background: black
antialias: ssaa
layers:
  - {type: iso, field: Q, level: -0.1}
```

Code: `flowreel.scene.shot` (`load`, `from_dict`), `flowreel.scene.timing`,
`flowreel.scene.plan`, `flowreel.scene.layers`.

## Keys

| Key | Type | Default | Example |
|---|---|---|---|
| `name` | string | required | `name: bare_reveal` |
| `source` | `adapter:location`, or a mapping of the adapter's options with `adapter` | required | `source: vtk:run/flow.pvd` |
| `time` | mapping, see below | required | `time: {frozen: 5000, frames: 120}` |
| `camera` | mapping (`view`, `track`, ...) | `{}` | `camera: {view: main}` |
| `size` | `[width, height]`, whole pixels | `[1920, 1080]` | `size: [1280, 720]` |
| `crop` | a box `{x: [lo, hi], y: [...], z: [...]}`, or `{around: {body, station}, half: [hx, hy, hz]}`, a window that travels with a body ([long bodies](long-bodies.md)) | none: the whole domain | `{x: [-1, 13], y: [-6, 6], z: [-2, 25]}` |
| `background` | colour | `black` | `background: '#101010'` |
| `antialias` | `none`, `fxaa` or `ssaa` | `ssaa` | `antialias: fxaa` |
| `lights` | `default`, `raking` or a list (see [cameras](cameras.md#lights)) | none: VTK's own light kit | `lights: raking` |
| `stretch` | `{x: 0.05}`: the model drawn scaled along axes, with a note in the frame ([long bodies](long-bodies.md#stretch)) | none | `{x: 0.1, note: false}` |
| `watermark` | a signature, logo or line of text drawn into every frame, scaled in drafts ([watermark](captions.md#the-watermark)) | none | `{text: 'A. Periyal', corner: lower_right, size: 28}` |
| `layers` | list of layers, drawn bottom first, at least one | required | see below |

`source` in its short form gives the adapter one location (a path, or a body name for
`geometry`). When the adapter needs more, write the mapping form: `adapter` plus the
adapter's options ([sources](sources.md)), for example
`source: {adapter: vtk, path: "flow_*.vti", body: body.vtp}`. A relative `path`, and a
relative `body` file for any adapter but `geometry`, is taken from the shot file's
folder, so a shot and its data can move together.

`crop` is passed to the source, which applies it while reading where the format allows, so
a small box also means less memory. `camera` takes a view, a camera track or a fit, and
may follow a body; its keys are in [cameras](cameras.md#a-shots-camera). Body names in
layers and in `follow` are those declared in the project's `flowreel.yml`, or the
source's own zone names ([bodies](bodies.md)). Without
`lights` the shot keeps VTK's own light kit, which the reveal's golden frame was drawn
with. To render a shot, see [rendering](rendering.md).

## Time

Exactly one of three forms picks the simulation step of each frame. Fields are never
interpolated: a frame always shows a saved step.

| Form | Keys | Frames | Example |
|---|---|---|---|
| `steps` | `steps: [first, last]`, `every` (whole number, default 1) | one per saved step in the range, keeping every `every`-th | `{steps: [5000, 5600], every: 5}` |
| `frozen` | `frozen: step`, `frames` (default 1) | `frames` frames of the saved step nearest to `step` | `{frozen: 5000, frames: 120}` |
| `keys` | `keys: [[frame, step], ...]`, `ease` (default `linear`), `frames` | `frames`, or one more than the last key's frame | `{keys: [[0, 5000], [120, 5300]]}` |

`keys` is a time track (see [tracks](tracks.md)). Its default ease is `linear` so that flow
time runs at a constant rate. Between two saved steps it takes the nearer one, and an exact
tie takes the earlier, so a frame never shows the flow later than asked.

A frozen shot (all frames on one step) lets the renderer contour once and reuse the
surfaces ([rendering](rendering.md#frozen-shots-contour-once)).

## Layers

`layers` is a list of mappings. `type` names the layer type; the other keys are that
type's options. Most options are tracks, so `opacity: 1` and `opacity: {from: 0, to: 1,
frames: [0, 24]}` are both valid. Layer types are listed in the page of each layer family.

```yaml
layers:
  - {type: iso, field: Q, level: {keys: [[0, -0.1], [120, -1.0]], ease: out}}
```

To add a layer type in code, subclass `flowreel.scene.layers.Layer`, list its options
with `Option(name, kind, default, required, track, choices)` and decorate it with
`@register`. A layer draws with `draw(plotter, frame)`, where `frame` carries the step,
the time, the loaded data and the layer's option values at that frame.

## Frame plan

`flowreel.scene.plan.plan(shot, source)` returns the plan: `n_frames`, and for each frame
the step, its physical time and every layer option's value. It reads only the source's
step list and times, so it is cheap. A time that does not fit the saved steps is an error
that names the shot file.

## Errors

Every message names the file, the key path and what was expected, for example:

```
reveal.yml: layers[2].level: unknown key 'levl' (allowed: ...); did you mean 'level'?
reveal.yml: time.steps: no saved step in [9000, 9100] (saved: 0 to 5600)
```

Unknown keys and unknown choices suggest the nearest valid name. A YAML syntax error
names the file and line. A colon in an unquoted string (`Outlet: p = 0`) is a syntax
error: put the string in quotes.
