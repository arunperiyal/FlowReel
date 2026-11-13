# FlowReel: plan

A program for making films of flow simulations: rendered shots, 2D panels, layouts,
captions, freezes, sound and assembly, from simulation output. The command is
`flowreel`; the Python package is `flowreel`.

Written 2026-11-08 after the AFMS film, whose scripts are the working prototype
(`prototype/afms/`). Decisions taken are listed in Section 23; questions still open are
in Section 24.

## 1. Decision

**An independent program.** It reads flexflow's files itself and has no dependency on
flexflow, and flexflow has none on it.

- **Most of the work is not about flexflow.** Of the prototype, only the PLT reader, the
  case layout and the OTHD/OISD series belong to the solver. Shots, cameras, derived
  fields, panels, layouts, text, time edits, sound and assembly are the same for any
  data.
- **flexflow stays light.** Rendering, matplotlib text, ffmpeg and audio stay out of its
  environment unless flowreel is installed.
- **Different pace and different rules.** Film work changes daily and depends on
  content-keyed caches, measured lengths and checking stills; a solver toolkit needs none.
- **No wrapper.** flexflow has nothing to do with films; FlowReel's own shell gives the
  same convenience (Section 13).

## 2. Goals and non-goals

**Goals**

1. Reproduce the AFMS film from configuration files alone, with no shot-specific code
   except the parametric bodies.
2. Any solver: anything pyvista can read, plus adapters.
3. Every change after the first render is cheap: text, timing, music and layout rebuild in
   about a minute; a changed shot re-renders only that shot.
4. Runs headless on clusters (OSMesa or EGL), in parallel, with Slurm scripts written for
   it.
5. Correct by default: derived fields from velocity, measured lengths, caches that cannot
   go stale silently.
6. Not tied to the film's one short cylinder (Sections 5.4 to 5.6): any number of bodies,
   each with its own supports; slender bodies hundreds of diameters long; and bodies that
   the solver models by equations only, with no surface in its files.

**Non-goals**

- An interactive editor with a time line. Files are the interface; the camera editor is
  the only window.
- Video effects beyond fades: no transitions library, no colour grading.
- Being a general plotting tool. Panels cover what films need; studies keep their own
  plotting scripts.

## 3. Concepts

| Term | Meaning |
|---|---|
| **project** | A folder with `flowreel.yml` (paths, defaults), `cameras.yml`, `shots/`, `film.yml`, and output folders `frames/`, `clips/`, `cache/` |
| **source** | Where data comes from: an adapter and a location, written `adapter:location`, such as `flexflow:bare/BR0SG0U1P0` or `vtk:run/wake.pvd` |
| **step** | The solver's own counter (5000, 5005, ...). Sources map steps to **time** in the solver's units |
| **shot** | One continuous piece of picture: a time line, a camera and layers, rendered to a frame folder |
| **layer** | One thing drawn in a shot: an iso surface, a slice, the body, an outline, markers, a parametric body |
| **body** | A named structure in a source: a wall surface from the files, or a **virtual body** that exists only as equations and time series. Declared in `flowreel.yml` with its axis, size and supports |
| **support** | How an end or a point of a body is held (clamped, pinned, ...), drawn as a symbol |
| **station** | A position along a body's axis, in the source's length unit |
| **track** | Any property that changes along a shot: a value, keys with easing, or a time series |
| **view** | A camera: position, focal point, up, and a view angle or a parallel half-height |
| **panel** | A 2D picture drawn with matplotlib: a section, cuts side by side, a map, time series |
| **layout** | Several frame folders and panels tiled into one frame |
| **film** | Shots, cards and holds in order, with text, freezes, frame-rate changes, fades and sound |

**Three clocks, never mixed.** *Frames* count pictures in a shot from 0. *Steps* are the
solver's. *Seconds* are film time, used only in `film.yml`. Every config states which it
uses (`frames:`, `step:`, `seconds:` or `at:`), and the build converts once.

## 4. Architecture

```text
flowreel/
  sources/        adapters: base.py (the interface), flexflow/ (PLT, OTHD, OISD),
                  vtk.py, geometry.py, registry.py
  fields/         derived fields: registry.py, kinematics.py (gradient, vorticity, Q,
                  lambda2), wall.py (wall shear, skin friction, sectional forces)
  scene/          layers/ (iso, slice, body, outline, glyphs, markers, geometry,
                  pathlines), tracks.py, views.py, lights.py, render.py, backend.py
  cameras/        schema.py (cameras.yml), paths.py (keys, orbit, fit), project.py,
                  editor.py (the window), states.py (ParaView .pvsm and .py)
  compose/        layout.py, panels/ (section, cuts, map, series, strip), timing.py
  film/           schema.py (film.yml), text.py (captions, maths), shapes.py,
                  cards.py, timeline.py (rates, freezes, holds), audio.py, build.py,
                  check.py
  jobs/           slurm.py, partitions.py, memory.py
  cache.py        content keys
  cli.py          the commands
tests/            unit, fields against analytic flows, golden frames
```

Dependencies: numpy, scipy, pyvista and VTK, matplotlib, Pillow, PyYAML, ffmpeg on the
path. Audio is handled by ffmpeg, so no audio library is needed.

**Data flow.** source → fields → scene → frames → (compose) → frames → film → clips →
film.mp4. Each arrow is a folder on disk, so any stage can be rerun or replaced.

## 5. Sources

### 5.1 Interface

```python
class Source(Protocol):
    name: str
    def steps(self) -> list[int]: ...
    def time(self, step: int) -> float: ...
    def fields(self) -> list[str]: ...                        # names it can provide
    def flow(self, step: int, fields: list[str], crop: Box | None) -> pv.UnstructuredGrid: ...
    def bodies(self) -> list[str]: ...                        # names of the wall surfaces
    def body(self, step: int, name: str | None = None) -> pv.PolyData: ...  # one, or all merged
    def bounds(self) -> Box: ...                              # whole domain
    def series(self, name: str) -> pd.DataFrame: ...          # time column plus values
    def memory_per_step(self, crop: Box | None) -> float: ... # GB, for -j
```

- **Crop** is applied while reading where the format allows, so a frame never holds the
  whole domain when it needs a box (the prototype keeps cells with every node inside).
- **Velocity is named `U`, `V`, `W`** or a vector `velocity`; adapters map their own
  names. Pressure is `p`.
- **Units** are the source's. A `scales:` block in `flowreel.yml` can declare
  `length: D`, `velocity: U` for labels.

### 5.2 Adapters

| Adapter | Location | Reads | Lives in |
|---|---|---|---|
| `flexflow` | a case folder | `binary/riser.<step>.plt`, zones `FIELD` and `cyl`, OTHD probes and OISD forces | FlowReel (its own PLT reader, from `prototype/afms/fxplt.py`) |
| `vtk` | `.pvd`, or a pattern like `out/wake_*.vtu` | pyvista; body from a second file or a named block | flowreel |
| `geometry` | a body name and parameters | nothing; builds the surface in code | flowreel |
| `openfoam` | a case folder | pyvista's OpenFOAM reader | later |

Adapters register under the entry point group `flowreel.sources`, so a new format can be
added as a plugin without changing FlowReel.

**First release:** the formats this film used, and nothing else: flexflow PLT (binary
Tecplot with a volume zone and a body zone), its OTHD probe and OISD force files, and CSV
time series. `vtk` and `geometry` come with them, the first because it costs little and
lets the tests use small files, the second because the carving shot needs it.

**Suggested next**, in order of how often flow codes write them:

| Format | Written by | Why |
|---|---|---|
| VTU/VTP series with `.pvd` | most research codes, ParaView exports | the common denominator; already in `vtk` |
| OpenFOAM case | OpenFOAM | widely used; pyvista reads it |
| XDMF with HDF5 | many HPC codes (FEniCS, Nek5000 tools) | large time series without one file per step |
| CGNS | commercial and aerospace codes | a standard for CFD meshes and solutions |
| EnSight Gold | Fluent, STAR-CCM+, Code_Saturne exports | the usual export from commercial solvers |
| ASCII Tecplot | older codes | close to the binary reader |

### 5.3 The geometry source

Parametric bodies for shots that need no data. A body is a function from parameters to a
surface, with parameters as tracks. First body: `grooved_cylinder` (span, radius, groove
count, depth, width, turns, phase, `cut_front` for carving, glow behind the cutters),
which is `render_carve.py` today. Later: `straight_grooved_cylinder`, `smooth_cylinder`,
`box`.

### 5.4 Bodies

A PLT file says where a body's surface is and nothing else: not which way its span runs,
not how thick it is, not how its ends are held. Those are declared once, in
`flowreel.yml`, and every shot, panel and data command uses them by the body's name.

```yaml
bodies:
  riser:
    zone: cyl                      # surface zone in the source; default: the body's name
    axis: x                        # span direction; leave out for a body that is not slender
    diameter: 1.0                  # reference length: symbols and stations scale with it
    ends:
      - {at: 0.0, support: pinned}
      - {at: 500.0, support: pinned, tension: true}
    series: {displacement: othd_files/riser1.othd, force: oisd_files/riser1.oisd}
  downstream:
    zone: cyl2
    axis: x
    diameter: 1.0
    ends: [{at: 0.0, support: clamped}, {at: 12.0, support: clamped}]
```

- **Any number of bodies.** A layer, a view's `follow`, a wall field and a panel each
  take `body: NAME`; with one body declared the name may be left out. Two cylinders in
  tandem are two entries, each with its own colour, supports, forces and series.
- **No declaration is needed to draw a body.** A source's surface zones are bodies under
  their zone names, as in Phase 1. The declaration adds what the files cannot say.
- **Series belong to a body:** `source.series("displacement", body="riser")`. A body's
  probes and forces are found by the files named here, since the solver names them by
  its own counter (`riser1`, `riser2`), not by zone.
- **Stations.** Where a body has an `axis`, its centre at a station is the centroid of
  its surface in a thin strip there, so `follow`, `supports` and `centreline` work on a
  bent and moving body.

**Supports.** The solver's boundary conditions on the structure are not in the PLT file,
so they are declared, and drawn by the `supports` layer (Section 7.2) at the body's
position in each frame.

| `support` | Fixes | Drawn as |
|---|---|---|
| `clamped` | position and slope | a block the body runs into (the prototype's clamps) |
| `pinned` | position; the body may turn | a cone with its tip on the axis, on a small base |
| `roller` | position across `free_along`; slides along it | the pinned cone on rollers |
| `spring` | nothing; restrained by `stiffness` | a coil from the body to a ground block |
| `free` | nothing | nothing, or a thin ring with `mark: true` |
| `prescribed` | moved by the solver along `direction` | a double arrow |

`tension: true` adds an arrow along the axis, for a riser held by top tension. A support
may also sit along the span (`at:` any station), for a body held at several points.
Symbols are sized in diameters, so they look the same on a body 12 or 500 diameters
long, and `min_pixels` keeps them readable in a view of the whole span. Supports are a
registry like bodies and layers: a new kind is a function, not a change to FlowReel.

### 5.5 Virtual bodies

Some structures are solved as equations coupled to the flow and never meshed: a pendulum
hung from a cylinder, a tuned mass, a spring to ground. The PLT file has no surface for
them; their motion is in the solver's time series (OTHD). A virtual body is drawn from a
**shape**, a body function from Section 5.3, whose parameters are **driven** by series.

```yaml
bodies:
  pendulum:
    virtual: true
    shape: pendulum                          # rod and bob
    params: {length: 2.0, bob: 0.3}
    attach: {body: riser, station: 250.0}    # its origin follows the riser there
    drive:
      angle: {series: pendulum.displacement, column: theta}
```

- **`attach`** puts the shape's origin on a real body's centre at a station, or at a
  fixed point; **`drive`** takes parameters from a series at each frame's time
  (a series track, Section 7.3). Nothing else is computed: FlowReel draws the solver's
  result and does not integrate the pendulum's equation.
- **Drawn to look modelled, not meshed:** a `ghost` style by default (translucent, with
  an edge line), so the film does not suggest the pendulum disturbed the flow as a solid
  would. A caption can say so.
- **First shapes:** `pendulum`, `spring`, `mass`. A shape is a registered function, so a
  new mechanism is a small plugin.
- A virtual body has series but no wall fields: asking for its wall shear is an error.

### 5.6 Long bodies

The reference film's cylinder is 12 diameters long and fits in one frame with its wake.
A riser 500 diameters long does not: in a view of the whole span the body is two pixels
thick, its motion (about one diameter) is invisible, and one saved step is too large to
load whole. The plan for such cases:

| Need | Answer | Where |
|---|---|---|
| See the flow somewhere along the span | a **window**: `crop: {around: {body: riser, station: 250}, half: [10, 6, 15]}` follows the body; the camera's `follow` uses the same station | 7.1, 7.4 |
| Travel along the span | `station` is a track, so the window and camera move from one end to the other | 7.3, 7.4 |
| See the shape of the whole span | the `centreline` layer: the body's axis as a tube, with `amplify` to draw its displacement many times larger, the rest line and the envelope | 7.2 |
| Fit the whole span in a frame | `stretch: {x: 0.05}` on a shot draws the model with one direction compressed, and says so in the frame | 7.4 |
| Several stations at once | a `stations` layout tiles one shot at several stations; a `locator` panel shows the span as a bar with the windows marked | 9 |
| Span against time | the `map` panel with displacement or sectional force from the probes | 9.2 |
| Files too large to load | windowed reading: only the window's nodes and the asked fields leave the disk | 17 |

- **`amplify` is for the body alone.** A displacement drawn 50 times larger no longer
  matches the flow around it, so `amplify` is allowed on `centreline` and on a `body`
  layer only in shots with no flow layers; otherwise it is an error.
- **The centreline can come from the probes** (OTHD) and not the PLT files, so a shot of
  the whole span's motion over thousands of steps reads no flow data at all.
- **Lengths in the files stay in the source's unit.** A station is a number, not a
  formula; `diameter` gives labels and symbols their scale.

## 6. Derived fields

**Rule:** derived fields are computed from velocity and pressure, never taken from a
solver's stored derived fields unless the adapter vouches for them. In flexflow's PLT
files the stored vorticity and Q are nodal sums, multiplied by the number of elements at
each node; at the wall this made the shear 4.6 times too large on bricks and 18.5 times
on tetrahedra, and wrong in direction on the helical case.

| Field | Definition | Needs |
|---|---|---|
| `velocity_gradient` | point gradient of velocity (VTK, mean of element gradients) | velocity |
| `vorticity`, `_x`, `_y`, `_z` | curl of velocity | gradient |
| `Q` | half of the squared rotation norm minus the squared strain norm | gradient |
| `lambda2` | middle eigenvalue of S squared plus Omega squared | gradient |
| `speed`, `velocity_relative` | magnitude; velocity minus the body's | velocity, body motion |
| `wall_shear`, `skin_friction` | tangential part of mu (grad u + grad u^T) n at the wall, over q | gradient on wall nodes |
| `pressure_coefficient` | (p - p_inf) / q | pressure |
| `sectional_force` | traction integrated over strips along an axis | wall shear, pressure |

Each field declares what it needs; a frame asking for `lambda2` and `vorticity_x`
computes the gradient once. The wall fields are `surface_data.py` today, checked by
integrating the traction: within 4% of the solver's forces on the bare case.

## 7. Scene

### 7.1 Shot file

```yaml
name: bare_reveal
source: flexflow:bare/BR0SG0U1P0
time: {steps: [5000, 5600], every: 5}        # or {frozen: 5000}, or {keys: ...}
camera: {view: main}                         # or {track: domain}
size: [1920, 1080]
crop: {x: [-1, 13], y: [-6, 6], z: [-2, 25]}
background: black
antialias: ssaa
layers: [...]
```

### 7.2 Layers

Every property below may be a track.

| Layer | Properties |
|---|---|
| `iso` | field, level, colour_by, range, colormap, opacity, wall_gap, near_wall, clip (plane or another layer), grow (axis, fraction), grey (blend to a flat colour), smooth shading, specular |
| `slice` | normal, position, field, range, colormap, fade_weak (values that become transparent), mask near the wall, opacity, triangulate |
| `body` | body (a name, a list, or all), colour, opacity, field and range on the surface, zero contour (colour, width), raking light, `amplify` (Section 5.6), style `solid` or `ghost` |
| `supports` | body, which ends, size in diameters, `min_pixels`, colour, opacity (Section 5.4) |
| `centreline` | body, from `surface` or `probes`, radius, colour by a value per station, `amplify`, rest line, envelope over a range of steps (Section 5.6) |
| `outline` | bounds (`domain`, `crop` or numbers), colour, width, opacity |
| `glyphs` | where (a face of the domain with a grid, or points), direction, size, colour, opacity |
| `markers3d` | `arrow3d`, `block`, `sphere`, `dimension3d`, `label3d`, each at model positions |
| `geometry` | a body from the geometry source, with its parameters |
| `pathlines` | seeds, length in steps, colour by, width (needs every step saved) |

### 7.3 Tracks

```yaml
opacity: 1.0                                           # fixed
position: {from: 0.02, to: 6.0, frames: [48, 72]}      # two keys, eased
grey: {keys: [[0, 0], [58, 0], [72, 1]]}               # any number of keys
level: {keys: [[0, -0.1], [120, -1.0]], ease: out}
```

- **Types:** number, vector, colour, boolean, choice. Colours blend in linear RGB.
- **Easing:** `linear`, `smooth` (smoothstep, the prototype's), `in`, `out`, `in_out`
  (cubic), or `hold` (steps).
- **Clamping:** before the first key a track holds the first value, after the last the
  last.
- **Series as a track:** `angle: {series: pendulum.displacement, column: theta}` takes the
  value from a body's time series at the frame's time, interpolated between samples, with
  optional `scale` and `offset` and nothing more (no expressions, Section 21). This is
  what moves a virtual body, and it can drive any property: an arrow's length from a
  force, a marker's height from a probe.
- **Time as a track:** `time: {keys: [[0, 5000], [120, 5300]]}` maps frames to steps;
  between saved steps it takes the nearer step (no interpolation of fields).

### 7.4 Views and lights

- **Perspective** (`view_angle`) or **parallel** (`parallel_scale`, half the frame
  height in model units), as flexflow's camera frames already store.
- **Fit:** `{fit: domain, direction_of: main, margin: 1.1}` places the camera along a
  view's direction far enough to show a box: used for the wide domain view.
- **Follow:** `{follow: riser, station: 6.0}` keeps the focal point on a named body's
  centre at a station, for close views of a moving body. `station` may be a track, so the
  camera travels along a long span; `motion: false` follows the station but not the
  body's vibration, so the vibration stays visible.
- **Stretch:** `stretch: {x: 0.05}` on a shot scales the drawn model along an axis, after
  contouring, to fit a long body in the frame. The frame carries a note of the scale,
  because a stretched wake is not the wake's true shape.
- **Lights:** default kit, or `raking` (a strong side light and a weak head light), or a
  list of lights. Optional ambient occlusion where the backend has it.

### 7.5 Rendering

- **Backend:** with no display, OSMesa when installed (faster on the workstation),
  otherwise EGL (airavata). `--backend` forces one.
- **Parallel:** a process per frame, `-j` jobs; threads per job default to a few, so `-j`
  sets the load.
- **Frozen shots** contour once and cache the surfaces (key: source, step, field, level,
  crop); only the camera and cheap properties change per frame.
- **Output:** `frames/<shot>/frame_00000.png`, padded; existing frames are skipped
  unless their key changed (Section 11).
- **Draft size:** `shot render --scale 0.5` (or `--size W H`) draws the same shot with
  fewer pixels, for a quick look or a small copy to share. The size is the only thing
  that changes: camera, view angle and line widths in model units stay, and widths given
  in pixels are scaled with it. Draft frames go to `frames/<shot>@<W>x<H>/`, so they
  never mix with the full-size frames or make them look stale.

## 8. Cameras

### 8.1 cameras.yml

Views are flexflow camera frames (`position`, `focal`, `up`, `view_angle`, `parallel`,
`parallel_scale`), so a file written by `flexflow field render --pick-camera` is a valid
single view, and ParaView `.pvsm` or `.py` states can be imported (flexflow's
`camera.py` already reads them).

```yaml
views:
  - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
  - {name: top, position: [6, 40, 9.5], focal: [6, 0, 9.5], up: [0, 0, -1],
     parallel: true, parallel_scale: 10.6}
tracks:
  carve:
    frames: 288
    path: linear                  # or spline (Catmull-Rom through the keys)
    keys:
      - {frame: 0, view: carve_wide}
      - {frame: 218, view: carve_close}
      - {frame: 241, view: carve_close}
      - {frame: 282, view: main}
```

### 8.2 Camera commands

- `camera path`: fills a track between keys, with easing per segment.
- `camera orbit`: writes an arc round a target (a point, or the body at a station) with
  radius, elevation from and to, span lead and frame count.
- `camera project`: prints where model points land on screen for a view or for every
  frame of a track, for placing captions and arrows.
- `camera import`: a ParaView state or a flexflow cam.yml into a named view.

### 8.3 Camera editor

A window that stays open and collects views into one file.

- **Buttons and keys:** *Save view* (`s`), *Undo* (`u`), *Replace* nearest (`r`),
  *Play* the track (`p`), *Next step* (`n`).
- **Sliders:** *Frame* that the next saved view belongs to; *Time step* to frame a view
  against the flow at several moments (each step loads once).
- **On screen:** views saved, current frame, step, and the projected positions of named
  anchors if the shot has captions.
- **Without a display or the data:** `--vtp` opens saved surfaces instead. Render a few
  steps where the data is, copy the `.vtp` files, pick on the laptop.

## 9. Compose

### 9.1 Layouts

```yaml
size: [1920, 1080]
tiles:
  - {frames: frames/bare_panel, at: [0, 0], size: [1280, 540]}
  - {frames: frames/helical_panel, at: [0, 540], size: [1280, 540]}
plots: {at: [1280, 0], size: [640, 1080], file: plots/compare.yml}
```

Any number of tiles; `grid: [rows, cols]` places them automatically. `stations:
{shot: shots/window.yml, at: [50, 250, 450]}` tiles one shot rendered at several stations
of a long body (Section 5.6), each tile labelled with its station. Tiles that lack a
frame at some index are an error unless `missing: hold` is set.

### 9.2 Panels

Matplotlib figures drawn per frame, sharing one style block (fonts, colours, maths font).

| Panel | Shows | Prototype |
|---|---|---|
| `section` | a cut: contours, streamlines relative to the moving body, an inset that follows the body, its box on the main view | groove section |
| `cuts` | the same cut at several stations side by side, labelled | span slices |
| `strip` | the body from one side, coloured by a surface field, zero contour | separation line |
| `map` | a field against two axes (span and time), filling in to the current frame | lift map |
| `series` | time series to the current time, a dot at the current value; one or several bodies | comparison plots |
| `locator` | a long body's span as a bar: its shape now (amplified), its supports, the windows on show | new |
| `phase` | one series against another (a pendulum's angle against the cylinder's displacement), a dot at the current time | new |

### 9.3 Panels at the output rate

When a panel is laid over frames that the film interpolates (8 to 24 fps), it is drawn
for every output frame, with time between flow frames and held through freezes; drawn at
8 fps and interpolated, its dots and line ends smear. The layout marks such panels
`rate: output`, and the film build draws them after it knows the freezes.

## 10. Film

### 10.1 film.yml

```yaml
output: film.mp4
fps: 24
size: [1920, 1080]
style:
  fonts: {regular: Lato-Regular.ttf, light: Lato-Light.ttf, maths: Lato}
  colours: {text: "#f2f2f2", muted: "#96a5b2"}
  caption: {size: 50, shadow: true, fade: 0.8}
audio:
  - {file: assets/nastelbom-background-music-602454.mp3, volume: 0.8,
     fade: [1.5, 4], licence: "Pixabay Content License"}
shots:
  - {name: opening, card: cards/opening.yml, seconds: 7, fade: [1.5, 1.5]}
  - {name: domain, frames: frames/bare_domain, fade: [1.5, 0], text: text/domain.yml}
  - name: compare
    frames: frames/compare
    rate: {fps: 8, to_output: interpolate}
    overlay: {plots: plots/compare.yml, at: [1280, 0]}
    freezes: [{at: 5.0, hold: 6.0, text: text/freeze_motion.yml}]
  - {name: end, hold_last_of: liftmap, seconds: 13, fade: [0, 2], fade_out_at: 0.5}
```

Text may sit in the shot or in separate files under `text/`, so the person writing the
words never edits the shot list.

### 10.2 Frame rate per shot

| `to_output` | Use for |
|---|---|
| `interpolate` | smooth flow frames; motion-compensated, scene cuts off |
| `repeat` | anything redrawn each frame (streamlines), or deliberate stepping |
| `blend` | soft cross-fade between frames |

### 10.3 Freezes and holds

- **Freeze:** stop a shot at a time for a hold, with its own text; later captions count
  time including it.
- **Hold:** a shot made of another shot's last frame, with or without its overlays.

### 10.4 Captions

| Field | Meaning |
|---|---|
| `lines` | one string per line; `$...$` is mathematics in the maths font |
| `at` | `[start, end]` in seconds; `end` may be `{shot: NAME, at: S}` to run across a cut |
| `place` | `top`, `bottom`, `centre`, `[x, y]`, `[centre, y]`, or `{model: [x, y, z], view: V, offset: [dx, dy]}` |
| `size`, `align`, `colour`, `box`, `shadow` | look |
| `shapes` | annotations (Section 12) |
| `id` | to refer to a caption from another shot |

Text is drawn by matplotlib so maths and the text font match; layout uses measured
extents, so centring and boxes fit the drawn text.

### 10.5 Cards

A card is a layout of blocks on a background: logo, title, divider, labelled name lists,
small print. The opening and end cards are cards, not special code, so a different
competition's layout is a different file.

### 10.6 Audio

- One or more tracks, each with file, offset into the track, start in the film, volume,
  fades.
- Lengths are **measured** from the files (the prototype's planned and actual lengths
  differed by a second); a fade ends with the shorter of picture and track.
- Later: ducking under narration, and a `--mute` build.

### 10.7 Build

1. Read and check every file; unknown keys are errors, with the nearest valid key
   suggested.
2. For each shot: build the base clip (frames, rate, freezes, overlays drawn at the
   output rate), keyed by content.
3. Fades on the picture, then text and shapes on top, so text can sit on black.
4. Join clips without re-encoding; add audio; write `film.mp4`.
5. Print planned and measured length per shot.

Outputs besides the film: `film.srt` from the captions, `contact.png` from `film check`.

**Preview copy.** `film build --preview 480` writes a small, strongly compressed copy
(`film_480p.mp4`) next to the film, for sending to someone; the number is the height in
pixels and the width follows the film's aspect ratio. It is made from the same clips as
the full film, scaled and encoded once at the join, so no frame is drawn again and the
text, laid out in the film's own pixels, shrinks with the picture and stays in place.
`--crf N` sets the quality (default 28 for a preview). The prototype had no such option:
its size was fixed in the scripts, and a small copy meant running ffmpeg by hand on the
finished film.

## 11. Caching

Every cached thing has a key from everything that changes it.

| Cached | Key |
|---|---|
| frozen surfaces | source, step, field, level, crop, field code version |
| frames | shot file section for that frame, track values, view, source step, code version |
| base clips | frame names and modification times, rate mode, freezes, filter chain, overlay settings |
| held frames | the held frame's modification time and its overlay settings |
| panels | panel settings, times, style |

`flowreel clean` removes caches; `--force` on any command ignores them. The prototype's
bugs were stale clips keyed by names only; content keys prevent that class of bug.

## 12. Annotations

- **2D, on the frame,** in pixels: `arrow` (from, to, width, head), `line`, `box`,
  `circle`, `ellipse`, `bracket`, `dimension` (ends and a value), `highlight` (dims
  outside a box).
- **3D, in the scene,** in model units: `arrow3d`, `block`, `outline`, `dimension3d`,
  `marker` (glowing points), `label3d` (projected text, drawn in 2D).
- **Anchored 2D:** any 2D point may be `{model: [x, y, z], view: V}` and is projected per
  frame, so an arrow follows a moving camera.

```yaml
- lines: ["Each groove $0.08D$ deep and $0.2D$ wide"]
  at: [8.4, 10.6]
  place: [1080, 50]
  box: true
  shapes:
    - {arrow: {from: [1250, 150], to: {model: [6, 0.42, 0.18], track: carve}, width: 4}}
```

## 13. Commands

The command layer is **shellkit** (`/media/arunperiyal/Works/projects/shellkit`):
argparse commands in a registry, run one at a time from the shell prompt
(`flowreel shot render carve.yml`, as Slurm jobs need) or in FlowReel's own interactive
shell when started with no arguments. The shell's contexts suit iterative film work:

```text
╭─ ~/films/afms [project:afms shot:carve]
╰─❯ shot preview; film check --at caption
```

Contexts: `project` (a folder with `flowreel.yml`), `shot`, `source`, `view`. Commands
keep their work in plain functions (`flowreel.film.build(...)`), so the library is usable
from Python without the shell, and the shell stays a thin layer.

```text
flowreel project  init | info | clean
flowreel camera   edit | path | orbit | project | import | preview
flowreel shot     render | preview | template | memory
flowreel compose  layout | panel | plot
flowreel film     build | check | lengths | srt | template
flowreel data     series | surface
flowreel jobs     write | submit
```

| Command | Options | Does |
|---|---|---|
| `shot render SHOT.yml` | `-j N`, `--frames A:B`, `--scale S`, `--size W H`, `--backend`, `--force`, `--slurm FILE`, `--submit` | renders a shot's frames, at a draft size when asked |
| `shot preview SHOT.yml` | `--every 10`, `--scale 0.25` | small frames to check timing |
| `shot memory SHOT.yml` | | estimated GB per frame and a safe `-j` for this machine |
| `compose layout LAYOUT.yml` | `-o DIR` | tiles frame folders |
| `compose panel PANEL.yml` | `-j N`, `-o DIR` | draws a 2D panel per frame |
| `film build` | `--only SHOT`, `--mute`, `--force`, `--preview HEIGHT`, `--crf N` | builds the film, or a small copy of it to share |
| `film check` | `--at caption\|freeze\|every:S` | contact sheet of stills with text in place |
| `film lengths` | | planned and measured length per shot |
| `film srt` | | caption file for players |
| `data surface SOURCE` | `--steps A:B:E`, `-o DIR` | wall shear and sectional forces per step |
| `data series SOURCE` | `--name`, `-o FILE` | a source's time series to CSV |
| `camera project` | `--view V` or `--track T`, `--points ...` | screen positions of model points |

## 14. Relation to flexflow (no wrapper)

FlowReel does not import flexflow and flexflow does not import FlowReel.

- **Reading flexflow cases** is FlowReel's `flexflow` adapter, with its own copy of the
  PLT reader (the prototype's `fxplt.py`, itself a copy of flexflow's). If the solver's
  format changes, both readers change; a shared small package for the reader is an
  option later (Section 24).
- **Cameras:** a cam.yml written by `flexflow field render --pick-camera` is a valid
  FlowReel view, because FlowReel reads the same keys (`position`, `focal`, `up`,
  `view_angle`, `parallel`, `parallel_scale`). FlowReel's camera import also reads
  ParaView `.pvsm` and `.py` states, as flexflow's `camera.py` does.
- **Slurm:** FlowReel keeps its own partition table (`jobs/partitions.yml`), starting
  with airavata's `part1` (3 h), `part2` (24 h) and `part3` (72 h), 128 CPUs and 125 GB on
  `node1`, and Param Shakti's from flexflow's `hpc_partition.py`.

## 15. Configuration and validation

**YAML for every file, text included.** The prototype kept its text in TOML; YAML is the
better choice here:

- **Nested shapes read naturally.** An arrow is `{arrow: {from: [x, y], to: [x, y]}}`
  inside a caption inside a shot; TOML's inline tables cannot span lines, so the same
  thing becomes hard to read.
- **Maths is safe in single quotes.** `'rms $C_L$: 0.55 → 0.06'` and
  `'$12D \times 30D$'` need no escaping, as in TOML's literal strings.
- **Long text folds.** A `>` block holds a paragraph, such as an acknowledgement,
  without one string per line.
- **One format** for shots, cameras, layouts and the film, with `include:` to share
  styles and text between films.

The one trap, unquoted strings with a colon (`Outlet: p = 0`), is caught by validation,
which reports the line. Text files keep one caption per block so a writer never edits
the shot list.

- One schema module per file type, with defaults written out by `template` commands,
  commented.
- Errors name the file, the key path and the expected form; unknown keys suggest the
  nearest valid one.
- Every file may `include:` another, so styles and text can be shared between films.

## 16. Testing

- **Tracks, easing, projection, caption layout:** unit tests with exact values.
- **Derived fields against analytic flows:** solid-body rotation (lambda2 and Q known),
  plane shear (wall shear known, sign checked as in the separation note), a Burgers
  vortex.
- **Golden frames:** a handful of AFMS frames (a reveal frame, a frozen domain frame, a
  carving frame, a composed comparison frame) re-rendered and compared with a tolerance;
  the prototype's frames are the reference.
- **Film build on a tiny project** (three shots of 10 frames, two captions, a freeze,
  audio): checks lengths, caption timing and that caches rebuild when they should.
- **flexflow adapter:** a two-step cut-down case checked into the test data.

## 17. Performance

- Memory, not cores, limits `-j`: about 0.7 GB per bare frame and 2.2 GB per helical
  frame here. `shot memory` measures one frame and suggests `-j` for the machine.
- The prototype rendered the whole film in about 30 minutes on airavata's 128 cores and
  about 75 minutes on the workstation's 48 threads; flowreel should match that.
- Panels are drawn in parallel chunks; text and assembly take about a minute.
- **Long cases.** A PLT file stores each variable as one block, so a window is read
  without loading the zone: the coordinates are read once to choose the window's nodes
  and cells, the choice is cached (the connectivity does not change between steps; a
  margin covers the body's motion), and each frame then reads only those nodes of the
  asked variables through a memory map. Memory and time per frame follow the window,
  not the domain. `shot memory` reports both, and refuses a shot that asks for the whole
  domain of a case that cannot fit.

## 18. Packaging

- Repository at `/media/arunperiyal/Works/projects/FlowReel`, to be public on GitHub.
  `pyproject.toml`, installed with pip into the render environments (`flexflow_env` on
  the workstation and airavata).
- Dependencies: numpy, scipy, pyvista and VTK, matplotlib, Pillow, PyYAML, shellkit
  (which brings prompt_toolkit and rich), and ffmpeg on the path (conda-forge where the
  system has none, as on airavata).
- **Lato is bundled** in `src/flowreel/fonts/` (Regular, Light, Italic, Bold) with its
  SIL Open Font Licence, `OFL.txt`; the OFL allows bundling with software. FlowReel
  registers the fonts with matplotlib and Pillow at start, so text looks the same on
  every machine without installing fonts.
- **Not in the repository:** the prototype's logo, music and data. The logo is an
  institutional mark and the music's licence does not allow sharing the track on its
  own; examples use generated data and silence.

## 19. Building it

Each phase ends with something checkable.

| Phase | Builds | Done when |
|---|---|---|
| 0 | Tidy the prototype: cameras.yml, one frame description, settings out of code, one derive module, padded frame names | AFMS frames identical by image difference |
| 1 | Package skeleton, sources (interface, flexflow, vtk, geometry), fields, tracks | field tests pass; a reveal frame from vtk data matches |
| 2 | Scene: layers, views, rendering, caching; `shot render`, with a draft size (`--scale`, `--size`) | reveal, domain and carving shots match the golden frames |
| 2B | Bodies: declarations, supports, series tracks, virtual bodies, long spans (Sections 5.4 to 5.6) | a generated case renders: a pinned cylinder 500 diameters long with a second body and a driven pendulum |
| 3 | Compose: layouts (with `stations`), panels at the output rate (with `locator`, `phase`) | comparison and lift-map frames match |
| 4 | Film: text with maths, shapes, cards, rates, freezes, audio, `check`, `lengths`; a small preview copy (`film build --preview`) | the AFMS film rebuilt from files, same length, captions in place |
| 5 | Slurm (the flexflow adapter moved to Phase 1) | `flowreel shot render --submit` renders the AFMS reveal on airavata |
| 6 | Camera editor, anchored annotations, `srt` | a new camera track picked in the window and rendered |
| 7 | Documentation: a tutorial reproducing a short film from a public data set | a new user makes a 20 s film from the tutorial |

### 19.1 Phase 1 tasks

Stacked branches, in order (each PR targets the one before; the first targets `main`).
Branches 2 to 5 depend only on branch 1 (branch 6 was added after them), so they can be built in parallel by agents
(see `.claude/rules/git-workflow.md`) and then stacked in this order. One commit
per task; tick the box in that commit.

**Branch 1: `phase1/sources-interface`** (data model)
- [x] `Box` type (bounds, contains, crop helpers)
- [x] `Source` protocol as in Section 5.1
- [x] Adapter registry and the `flowreel.sources` entry-point group
- [x] Test fixtures: a small generated structured/unstructured flow with a body surface
- [x] Docs: sources page (interface, naming of `U V W p`, units)

**Branch 2: `phase1/sources-vtk-geometry`** (adapters, no solver files)
- [x] `vtk` adapter: `.pvd` and filename pattern, steps and time
- [x] `vtk` crop while reading, `memory_per_step`
- [x] `vtk` body from a second file or a named block
- [x] `geometry` adapter and the body registry
- [x] Body `grooved_cylinder` (parameters as tracks-ready values)
- [x] Tests and docs for both adapters

**Branch 3: `phase1/sources-flexflow`** (adapter for the solver)
- [x] Copy `prototype/afms/fxplt.py` into `sources/flexflow/plt.py`, with a docstring and tests
- [x] Cut a two-step PLT from real output (`ssh wsl` / `ssh airavata`) into `tests/data/`
- [x] Adapter: steps, time, fields, `flow` with crop, `body` (zone `cyl`), `bounds`
- [x] OTHD probe reader and OISD force reader in `series`
- [x] Map names to `U V W p`; keep stored derived fields out of the provided set (Section 6)
- [x] Tests and docs

**Branch 4: `phase1/fields-derived`** (algorithms)
- [x] Field registry with declared needs; the gradient computed once per frame
- [x] `velocity_gradient`, `vorticity` and components
- [x] `Q` and `lambda2`
- [x] `speed`, `velocity_relative`, `pressure_coefficient`
- [x] `wall_shear`, `skin_friction`
- [x] `sectional_force`
- [x] Analytic tests: solid-body rotation, plane shear (sign checked), Burgers vortex
- [x] Docs: definition, meaning and sign convention of each field

**Branch 5: `phase1/tracks-easing`** (animation values)
- [x] Track parsing: fixed, `from/to/frames`, `keys`
- [x] Easings: linear, smooth, in, out, in_out, hold
- [x] Value types: number, vector, colour (linear RGB), boolean, choice
- [x] Clamping and the time track (frames to steps, nearer step)
- [x] Exact unit tests; docs

**Branch 6: `phase1/general-bodies`** (any body, not only the cylinder; added 2026-11-13)
- [x] Interface: `bodies()` names and `body(step, name=None)`; `vtk` and `geometry` follow
- [x] `flexflow`: the volume zone and every surface zone found in the file, no `cyl` default
- [x] PLT writer; synthetic files with tetrahedra, a triangle wall and two body zones
- [x] Total force and moment on any body
- [x] Wall fields on a closed body with no axis: Stokes flow past a sphere
- [x] Docs

**Branch 7: `phase1/reveal-golden`** (depends on branches 2, 4, 5 and 6)
- [x] Generate small vtk data from the prototype's reveal case for the test
- [x] Golden reveal frame from airavata's `frames/`, downscaled, kept small
- [x] Minimal reveal render path using sources, fields and tracks
- [x] Image-difference test with tolerance (Section 21)

**Phase 1 is done when** all field tests pass and the reveal frame rendered from vtk
data matches the prototype's. **Done 2026-11-13:** the field tests pass and the reveal
frame matches (`docs/reveal.md`).

### 19.2 Phase 2 tasks

Stacked branches, in order (each PR targets the one before; the first targets `main`).
Branches 2, 3 and 4 depend only on branch 1, so they can be built in parallel by agents
and then stacked in this order. Branches 5, 6 and 7 are done in order by the main
session. One commit per task; tick the box in that commit.

**Branch 1: `phase2/scene-shot-file`** (data model)
- [ ] Validation helper: errors name the file and key path; unknown keys suggest the nearest (Section 15)
- [ ] Shot schema as in Section 7.1: name, source, time, camera, size, crop, background, antialias, layers
- [ ] Time of a shot: `steps` with `every`, `frozen` with a frame count, `keys`
- [ ] Frame plan: for each frame, its step and the value of every track
- [ ] Layer interface and registry: a layer takes the frame's data and values and adds actors to a plot
- [ ] Docs: shot file reference (type, default and example per key)

**Branch 2: `phase2/scene-views`** (cameras and lights; needs branch 1)
- [ ] View: perspective and parallel, flexflow's camera keys; `cameras.yml` views (Section 8.1)
- [ ] Camera track between named views: linear and spline path, eased
- [ ] `fit`: along a view's direction, far enough to show a box
- [ ] `follow`: focal point on a body's centre at a station
- [ ] Lights: default kit, `raking`, or a list
- [ ] Projection of model points to the screen, with exact tests
- [ ] Docs: cameras page

**Branch 3: `phase2/layers-flow`** (layers that draw the flow; needs branch 1)
- [ ] `iso`: field, level, colour_by, range, colormap, opacity, wall_gap
- [ ] `iso`: clip by a plane, `grow` along an axis, `grey`
- [ ] `slice`: normal, position, field, range, fade_weak, mask near the wall
- [ ] `body`: one named body, a list or all; colour, opacity, field and range on the surface, zero contour
- [ ] Reveal look written as a shot file on these layers; `reveal.py` goes, its golden test stays
- [ ] Docs: these layers, with an example on generated data

**Branch 4: `phase2/layers-markers`** (layers without flow data; needs branch 1)
- [ ] `outline`: bounds from `domain`, `crop` or numbers; colour, width, opacity
- [ ] `glyphs`: arrows on a face of the domain or at points
- [ ] `markers3d`: `arrow3d`, `block`, `sphere`
- [ ] `geometry`: a body from the geometry source, parameters as tracks, colour by its arrays
- [ ] Docs: these layers, with an example on generated data

**Branch 5: `phase2/render-cache`** (rendering; needs branches 2, 3 and 4)
- [ ] Backend choice: OSMesa when installed, else EGL; `backend` forces one
- [ ] `scene.render_frame(shot, frame)` and `scene.render(shot, ...)`: a process per frame, `jobs`, threads per job
- [ ] Frame keys (Section 11): frames are skipped unless their key changed; `force`
- [ ] Frozen shots contour once and cache the surfaces
- [ ] Draft size: `scale` and `size`, frames in `frames/<shot>@<W>x<H>/` (Section 7.5)
- [ ] Memory of one frame measured, and the safe number of jobs
- [ ] Tests on generated data; docs: rendering and caching

**Branch 6: `phase2/cli-shot`** (commands; needs branch 5)
- [ ] `flowreel` entry point on shellkit: one-shot and interactive
- [ ] `shot render` with `-j`, `--frames`, `--scale`, `--size`, `--backend`, `--force`
- [ ] `shot preview` (`--every`, `--scale`) and `shot memory`
- [ ] `shot template`: a commented shot file with the defaults
- [ ] Help text; docs: commands page

**Branch 7: `phase2/golden-shots`** (the check; needs all the others)
- [ ] Small domain data and a golden domain frame drawn by the prototype's `render_frozen.py`
- [ ] Golden carving frame drawn by the prototype's `render_carve.py`
- [ ] Shot files for the domain and carving shots; `examples/` shot on generated data
- [ ] Image-difference tests of the three shots through `shot render`

Left out of Phase 2: the `pathlines` layer (no shot of the reference film uses it, and it
needs every step saved), `dimension3d` and `label3d` (they draw text, so they come with
Phase 4's text and Phase 6's anchored annotations), ambient occlusion, and `--slurm` and
`--submit` (Phase 5).

**Phase 2 is done when** the reveal, domain and carving shots, each rendered from a shot
file by `flowreel shot render`, match the golden frames.

### 19.3 Phase 2B tasks

Added 2026-11-13 for the studies after the film: long cylinders, pinned ends, cylinders
in tandem and bodies modelled by equations. It follows Phase 2 because it builds on
layers, views and rendering, and before Phase 3 because the panels there take bodies by
name. Branches 2 and 3 need only branch 1; branch 5 needs branch 1; branch 4 needs
branch 3.

**Branch 1: `phase2b/bodies-declared`** (data model)
- [ ] `flowreel.yml` schema with `bodies:`; a `Body` record (zone, axis, diameter, ends, series)
- [ ] Layers, `follow` and wall fields take a body by name; one body may go unnamed
- [ ] Centre of a body at a station, and its centreline, from the surface
- [ ] `series(name, body=...)`; flexflow finds each body's OTHD and OISD files
- [ ] Docs: bodies page

**Branch 2: `phase2b/layers-supports`** (needs branch 1)
- [ ] Support registry; `clamped` and `pinned`
- [ ] `roller`, `spring`, `free`, `prescribed`; `tension`
- [ ] `supports` layer: at the body's position per frame, sized in diameters, `min_pixels`
- [ ] The domain shot's clamps drawn by `supports`; its golden frame still matches
- [ ] Docs, with a picture of each symbol

**Branch 3: `phase2b/tracks-series`** (needs branch 1)
- [ ] Series track: value at the frame's time, `column`, `scale`, `offset`
- [ ] `centreline` layer from the surface: tube, colour by a value per station
- [ ] `centreline` from probes; `amplify`, rest line, envelope
- [ ] `amplify` on a `body` layer, refused in shots with flow layers
- [ ] Tests with exact values; docs

**Branch 4: `phase2b/bodies-virtual`** (needs branch 3)
- [ ] Virtual body in `bodies:`: `shape`, `params`, `attach`, `drive`
- [ ] Shapes `pendulum`, `spring`, `mass`
- [ ] `ghost` style; wall fields on a virtual body are an error
- [ ] Docs, with an example on generated data

**Branch 5: `phase2b/long-span`** (needs branch 1)
- [ ] Windowed PLT reading: nodes and cells of a box, only the asked variables, memory-mapped
- [ ] Cached window index, with a margin for the body's motion
- [ ] `crop: {around: ...}` and `follow` with `station` as a track, `motion: false`
- [ ] `stretch` on a shot, with its note in the frame
- [ ] `memory_per_step` and `shot memory` from the window; refusal of a shot that cannot fit
- [ ] Docs: long bodies page

**Branch 6: `phase2b/bodies-check`** (needs all the others)
- [ ] Generated case, written at test time by the PLT writer: a pinned cylinder 500 diameters long, a second body, probes, and a pendulum's series
- [ ] Shots of it: a travelling window, the whole span by `centreline`, the pendulum
- [ ] Tests: the frames render, the window reads a small part of the file, the pendulum follows its series
- [ ] `examples/` project on generated data

**Phase 2B is done when** those three shots render from the generated case and the
window shot's memory does not grow with the span.

## 20. From the prototype

| Prototype file | Becomes |
|---|---|
| `fxplt.py` | `sources/flexflow/plt.py`, the adapter's reader |
| `render_frames.py` | `scene/` layers iso, slice, body; views; backend |
| `render_frozen.py` | frozen time, camera tracks, outline, glyphs, markers |
| `render_carve.py` | `sources/geometry.py`, body `grooved_cylinder` |
| `surface_data.py` | `fields/wall.py`, `data surface` |
| `render_extras.py` | `compose/panels/`: section, cuts, strip, map |
| `compose_compare.py` | `compose/layout.py`, panel `series` |
| `make_film.py`, `film_text.toml` | `film/`, `film.yml` and `text/` |
| `extract_series.py` | the flexflow adapter's `series` (OTHD, OISD) |
| `render_airavata.slurm` | `jobs/`, through `--slurm` |

## 21. Risks

| Risk | Answer |
|---|---|
| Golden-image tests break on VTK or driver updates | compare with a tolerance; pin versions in the render environments |
| Configs grow into a programming language | no expressions; parametric bodies and new panels are Python plugins instead |
| Two copies of the PLT reader drift apart | the adapter's tests read a small PLT written by the solver; a shared reader package later if needed |
| Motion interpolation artefacts on fast flow | per-shot `to_output`; `film check` shows them before the final build |
| Licences of media | a `licence` field per asset, printed by `film check` and on cards when needed |

## 22. Prototype in this repository

`prototype/afms/` holds the AFMS film scripts as they were on 2026-11-08: the reference
for the golden-frame tests and for each phase's "done when". They stay unchanged; the
package is written fresh in `src/flowreel/` (Phase 0 tidying is done there, not in the
prototype). The film's own copy stays in the research repository as the record of the
submitted film.

## 23. Decisions

| Topic | Decision (2026-11-08) |
|---|---|
| Name | FlowReel (command and package `flowreel`) |
| Home | `/media/arunperiyal/Works/projects/FlowReel`; public on GitHub as `arunperiyal/FlowReel` |
| Licence | MIT for FlowReel's code; the bundled Lato fonts stay under the OFL |
| Users | Mostly Arun; public, so documentation enough for others to start |
| Relation to flexflow | Independent; no wrapper; FlowReel reads flexflow's files itself |
| PLT reader | FlowReel keeps its own copy, tested against a small PLT written by the solver |
| Data formats, first release | flexflow PLT, OTHD and OISD, CSV series; plus `vtk` and `geometry` |
| Config and text format | YAML everywhere (Section 15) |
| Command layer | shellkit, one-shot and interactive (Section 13); public on GitHub, installed from there |
| Camera editor | Desktop window |
| Fonts | Lato bundled with its OFL licence |
| Environment | The existing `flexflow_env` conda environment (Python 3.12) on the laptop, workstation and airavata |
| AFMS prototype | Stays in the research repository as the record of the submitted film; this repository has a copy in `prototype/afms/` |
| When | Starting now, with Phase 1 next |

## 24. Questions

New ones are added here as the work raises them.

| # | Question | Needed by |
|---|---|---|
| 1 | How does the solver write a virtual body's state (the pendulum): which file and block, which columns, an angle or a position? A sample file would settle it. | Phase 2B, branch 4 |
| 2 | With two cylinders, is each its own surface zone in the PLT, and does each have its own OTHD and OISD file (`riser1`, `riser2`)? | Phase 2B, branch 1 |
| 3 | For a 500 diameter case: nodes and size of one PLT file, how often steps are saved, and whether the whole domain is saved. This sets how far windowed reading must go. | Phase 2B, branch 5 |
| 4 | Which supports do the coming cases use besides pinned: top tension, rollers, springs, supports along the span? | Phase 2B, branch 2 |
| 5 | Supports are declared in `flowreel.yml`. Should they later be read from the solver's input files, and where are they written there? | after Phase 2B |
