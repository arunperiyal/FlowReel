# Shot files

A **shot** is one continuous piece of film: one source, one camera, a time, and a stack of
layers. It is one YAML file. Everything a shot can vary over time is a
[track](tracks.md), so the file holds the whole shot and no code does.

```yaml
name: bare_reveal
source: bare                    # a tag: data/bare/
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
| `source` | a tag, or `{tag, ...options}` | required | `source: bare` |
| `time` | mapping, see below | required | `time: {frozen: 5000, frames: 120}` |
| `camera` | mapping (`view`, `track`, ...) | `{}` | `camera: {view: main}` |
| `size` | `[width, height]`, whole pixels | the size of the box that shows it in a film of scenes; else `[1920, 1080]` | `size: [1280, 720]` |
| `crop` | a box `{x: [lo, hi], y: [...], z: [...]}`, or `{around: {body, station}, half: [hx, hy, hz]}`, a window that travels with a body ([long bodies](long-bodies.md)) | none: the whole domain | `{x: [-1, 13], y: [-6, 6], z: [-2, 25]}` |
| `background` | colour | `black` | `background: '#101010'` |
| `antialias` | `none`, `fxaa` or `ssaa` | `ssaa` | `antialias: fxaa` |
| `lights` | `default`, `raking` or a list (see [cameras](cameras.md#lights)) | none: VTK's own light kit | `lights: raking` |
| `stretch` | `{x: 0.05}`: the model drawn scaled along axes, with a note in the frame ([long bodies](long-bodies.md#stretch)) | none | `{x: 0.1, note: false}` |
| `watermark` | a signature, logo or line of text drawn into every frame, scaled in drafts ([watermark](../film/film.md#the-watermark)) | none | `{text: 'A. Periyal', corner: lower_right, size: 28}` |
| `layers` | list of layers, drawn bottom first, at least one | required | see below |

`source: bare` names a [tag](../projects/data.md#shots-and-panels-name-a-tag), a case of
the project under `data/bare/`: the shot then reads it with the tag's bodies and units,
and a reading option goes in the mapping form, `source: {tag: bare, margin: 1.0}`. The
forms that named the files (`source: vtk:flow.pvd`, `{adapter: ...}`) are not read: import
the case with [`data import`](../projects/data.md) and name its tag.

`crop` is passed to the source, which applies it while reading where the format allows, so
a small box also means less memory. `camera` takes a view, a camera track or a fit, and
may follow a body; its keys are in [cameras](cameras.md#a-shots-camera). Body names in
layers and in `follow` are those declared in the tag's `domain.yml`, or the
source's own zone names ([bodies](../projects/bodies.md)). Without
`lights` the shot keeps VTK's own light kit, which the reveal's golden frame was drawn
with. To render a shot, see [rendering](../making/rendering.md).

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
surfaces ([rendering](../making/rendering.md#frozen-shots-contour-once)).

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
