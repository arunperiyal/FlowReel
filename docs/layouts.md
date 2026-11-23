# Layouts

A layout puts several folders of frames side by side in one picture: two cases
compared, a wake beside its plots, or one shot seen at several stations of a long body
(plan Section 9.1). Each tile is a folder of `frame_00000.png` files, as
`shot render` writes them, and composed frame *i* puts frame *i* of every tile
together. `compose.layout` writes the composed frames into a frame folder of their
own, so a layout's output can be a tile of another layout, or a shot of the film.

A runnable example on generated frames is `examples/compose_layout/run.py`.

## A layout file

```yaml
size: [1920, 1080]
background: black
tiles:
  - {frames: frames/bare_panel, at: [0, 0], size: [1280, 540], label: bare}
  - {frames: frames/helical_panel, at: [0, 540], size: [1280, 540], fit: cover}
```

Positions and sizes are pixels of the composed picture. `at` is a tile's upper left
corner, x to the right and y down, as image files count. Tiles are drawn in order, so a
later tile lies over an earlier one where they overlap. Relative `frames` folders are
taken from the layout file's folder.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | the file's name without `.yml` | the output folder, `OUT/<name>/` |
| `size` | `[width, height]` | `[1920, 1080]` | the composed picture, pixels |
| `background` | colour | `black` | a colour name or `'#rrggbb'`; shows in gaps and bars |
| `grid` | `[rows, cols]` | none | place the tiles automatically (below) |
| `gap` | whole number | `0` | pixels between grid cells; only with `grid` |
| `missing` | `error` or `hold` | `error` | what a tile without frame *i* does (below) |
| `tiles` | list | required | the tiles: `frames`, `stations` and `panel` entries |

A `frames` entry:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `frames` | path | required | folder of `frame_NNNNN.png` |
| `at` | `[x, y]` | required without `grid` | upper left corner, pixels |
| `size` | `[width, height]` | required without `grid` | the tile, pixels |
| `fit` | `contain`, `cover`, `stretch` | `contain` | how a frame of another shape fills the tile |
| `label` | text or mapping | none | text over the tile |

`fit: contain` shows the whole frame, centred, with bars of the background; `cover`
fills the tile and cuts the overflow evenly from both sides; `stretch` changes the
frame's proportions. Frames are resized with a Lanczos filter, so a tile the frame's own
size shows it pixel for pixel. Rendering a shot at its tile's size is better than
resizing: `shot render --size W H` does that, and `stations` tiles do it on their own.

A `label` is `label: bare`, or a mapping:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `text` | string | required | the words |
| `corner` | `upper_left`, `upper_right`, `lower_left`, `lower_right` | `upper_left` | where |
| `size` | number | `28` | font size in pixels, in the bundled Lato |
| `colour` | colour | `'#ffffff'` | |

Labels sit half their size in from the tile's edges; a lower label stands on that line
by its baseline, so letters that hang below it (g, y) are not cut.

## Grid

```yaml
size: [960, 540]
grid: [2, 2]
gap: 6
tiles: [{frames: frames/a}, {frames: frames/b, label: b}, {frames: frames/c}]
```

`grid: [rows, cols]` fills cells row by row, in the order of `tiles`; `at` and `size`
are then left out. Cells split the picture evenly after the gaps. Edges are rounded to
whole pixels, so cells differ by at most one pixel and the last ones end on the
picture's edge. Cells may stay empty. More tiles than cells is an error.

## Frames by index, and `missing: hold`

Composed frame *i* takes frame *i* of every tile, and the composed frames are every
index that any tile has. A tile that lacks frame *i* is an error that names the tile,
the frame and the frames it has. The usual cause is a render that did not finish, and
a film quietly showing a stale frame there is the kind of fault the prototype had.

With `missing: hold`, such a tile shows its nearest earlier frame instead, or its first
frame before it starts. That is for tiles meant to be shorter: a title of one frame, or
a shot that stops while another goes on.

## One shot at several stations: `stations`

```yaml
size: [960, 180]
tiles:
  - stations: {shot: window.yml, at: [40, 100, 160]}
    at: [0, 0]
    size: [960, 180]
    along: row                     # or column
    label: 'x = {station:g}'
```

A `stations` entry makes one tile per station, from one shot of a long body (see
[long bodies](long-bodies.md)). The shot must move with a station: it crops around a
body (`crop: {around: ...}`) or its camera follows one (`camera: {follow: ...}`). For
each station, FlowReel takes a copy of the shot with that station, fixed, in the crop's
`around` and in the camera's `station` (when the camera gives its own; otherwise the
camera takes the crop's). The copy is named `<shot>_station<value>`.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `stations.shot` | path | required | the shot file, from the layout's folder |
| `stations.at` | list of numbers | required | stations, in the body's length unit |
| `at`, `size` | as above | required without `grid` | the area the tiles share |
| `along` | `row`, `column` | `row` | how the tiles split the area; not with `grid` |
| `fit`, `label` | as above | `label: 'station {station:g}'` | the label's text is formatted with `{station}`; `label: null` for none |

In a `grid`, a `stations` entry takes one cell per station. Otherwise its tiles split
its `at` and `size` evenly, with the layout's `gap`.

`compose.layout` renders each station's shot first, at its tile's size, into
`OUT/<shot>_station<value>@<W>x<H>/` (through `flowreel.scene.render`, which skips its
own fresh frames), then composes. Options for that render (`jobs`, `backend` ...) go in
`render={...}`.

## Panel tiles: `panel`

```yaml
size: [1920, 1080]
tiles:
  - {frames: frames/bare_wake, at: [0, 0], size: [1280, 1080]}
  - {panel: panels/lift.yml, at: [1280, 0], size: [640, 1080]}
```

A `panel` entry names a [panel file](panels.md). `compose.layout` draws the panel first,
into `OUT/<panel>/` (through `compose.panel`, which skips its own fresh frames), then
tiles its frames by index like any folder of frames: composed frame *i* shows the
panel's frame *i*, drawn at the panel's `times[i]`. Give the panel the times of the
shot beside it (`times: {shot: ...}`) and the two line up frame by frame.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `panel` | path | required | the panel file, from the layout file's folder |
| `rate` | `flow` or `output` | `flow` | `output`: drawn at the film's output frames (below) |
| `at`, `size`, `fit`, `label` | | | as for a `frames` entry |

The panel is drawn at its own `size` and fitted into the tile, so give it the tile's
size for a picture drawn pixel for pixel. Every frame of the panel is drawn, even when
only some composed `frames` are asked for, so its frames always match the other tiles'.
Options for drawing (`jobs`, `processes`) go in `panels={...}`.

## Panels at the output rate: `rate: output`

The film shows flow frames at a lower rate than it plays, 8 frames of flow a second in
a 24 frames a second film, and makes the frames between them by interpolation (plan
Section 10.2). A plot laid over such frames must not be interpolated too, or its dot
and line end smear between two places. A panel tile marked `rate: output` is instead
drawn for every output frame, at a time between the two flow frames around it, and held
through the film's freezes (plan Section 9.3).

The film describes its output frames as **positions**: one number per output frame,
the composed frame it shows, fractional between two of them, and repeated through a
hold. `compose.output_positions` makes them:

```python
from flowreel import compose

# 16 flow frames played at three times their rate, frozen for 12 frames at frame 5
output = compose.output_positions(16, per_frame=3, holds=[(5, 12)])
report = compose.layout("compare.yml", "frames", output=output)
for tile, panel in report.overlays:               # one rate: output tile each
    print(tile.at, tile.size, panel.folder)       # frames/lift_output/frame_00000.png ...
```

With `output`:

- the composed frames leave out the `rate: output` tiles; they hold the flow, at its
  own rate, for the film to interpolate. They go to `OUT/<layout>_flow/`, so they never
  replace the preview's frames in `OUT/<layout>/`, which show those panels;
- each such panel is drawn once per output frame into `OUT/<panel>_output/`. Output
  frame *j* is drawn at the time of position `output[j]`: the panel's `times[i]` at a
  whole position *i*, and linearly between `times[i]` and `times[i + 1]` between
  them. A position outside the panel's frames takes its first or last time;
- `report.overlays` lists each tile, with its place in the composed picture, and its
  panel's report, so the film can lay the frames over its own.

A `series` panel interpolates its values in time, so the dot of an output frame between
two flow frames lies between their values, where the flow is at that moment. Without
`output`, as in a preview of the layout, a `rate: output` tile is drawn and composed
like any panel tile. The film build passes `output`, since it knows the rates and
freezes.

## Composing: `compose.layout`

```python
from flowreel import compose

report = compose.layout("compare.yml", "frames")            # frames/compare/frame_00000.png ...
report = compose.layout("compare.yml", "frames", scale=0.5) # a draft, frames/compare@960x540/
print(report.count("composed"), report.count("skipped"))
```

| Argument | Meaning |
|---|---|
| `lay` | a layout file or a loaded `Layout` |
| `out` | folder of frame folders (default `frames`) |
| `frames` | only these composed frames (default all) |
| `force` | compose every frame again, and render the stations' frames again |
| `scale`, `size` | a draft: positions, tiles and labels scaled, into `OUT/<name>@<W>x<H>/` |
| `render` | options for the stations' renders |
| `panels` | options for drawing the `panel` tiles (`jobs`, `processes`) |
| `output` | the film's output frames as positions; `rate: output` tiles are then drawn at them (`report.overlays`) |

**Keys.** Each composed frame has a key (plan Section 11) from the layout's settings
(size, background, each tile's place, fit, label and station) and the resolved path,
size and modification time of each tile frame it shows. A frame whose file exists with
the same key is skipped. So re-rendering one tile's frame composes again only the
frames that show it, and an edit to the layout composes everything again. Keys are
kept in the output folder's `.keys.json`, as for shots.
