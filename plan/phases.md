# FlowReel plan: the phases and their tasks

Section 19: the phases, each split into branches of checkbox tasks. The plan's other parts are listed in [README](README.md).

## 19. Building it

Each phase ends with something checkable.

| Phase | Builds | Done when |
|---|---|---|
| 0 | Tidy the prototype: cameras.yml, one frame description, settings out of code, one derive module, padded frame names | AFMS frames identical by image difference |
| 1 | Package skeleton, sources (interface, flexflow, vtk, geometry), fields, tracks | field tests pass; a reveal frame from vtk data matches |
| 2 | Scene: layers, views, rendering, caching; `shot render`, with a draft size (`--scale`, `--size`) | reveal, domain and carving shots match the golden frames |
| 2B | Bodies: declarations, supports, series tracks, virtual bodies, long spans (Sections 5.4 to 5.6) | a generated case renders: a pin-roll cylinder 500 diameters long with a second body and a driven pendulum |
| 3 | Compose: layouts (with `stations`), panels at the output rate (with `locator`, `phase`) | comparison and lift-map frames match |
| 4 | Film: text with maths, shapes, cards, rates, freezes, audio, `check`, `lengths`, watermark (film and shot level); a small preview copy (`film build --preview`) | the AFMS film rebuilt from files, same length, captions in place (done 2026-11-21) |
| 5 | Slurm (the flexflow adapter moved to Phase 1) | `flowreel shot render --submit` renders the AFMS reveal on airavata (done 2026-11-21) |
| 6 | Camera editor, anchored annotations, `srt` | a new camera track picked in the window and rendered (done 2026-11-22) |
| 7 | Documentation: a tutorial reproducing a short film from a public data set | a new user makes a 20 s film from the tutorial |
| 8 | Editor and workflow improvements asked for while using FlowReel, collected as they come | each one checked as its task says; the list closed by Arun |
| 9 | Data by tag: a `data` command group, each case under `data/<tag>/` with its own `domain.yml`, shots naming a tag | branches 1 to 5 done, their tests and examples on tags (the tutorials move in Phase 10) |
| 10 | The film as levels: a film of scenes, a scene a layout of boxes (text, image, shape, shot, panel); `scene` and `panel` commands; a window to design a layout; the documentation and both tutorials rewritten | the AFMS film made from its cases as tags and scenes; both tutorials rewritten; the guide by levels |

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
frame matches (`docs/guide/reveal.md`).

### 19.2 Phase 2 tasks

Stacked branches, in order (each PR targets the one before; the first targets `main`).
Branches 2, 3 and 4 depend only on branch 1, so they can be built in parallel by agents
and then stacked in this order. Branches 5, 6 and 7 are done in order by the main
session. One commit per task; tick the box in that commit.

**Branch 1: `phase2/scene-shot-file`** (data model)
- [x] Validation helper: errors name the file and key path; unknown keys suggest the nearest (Section 15)
- [x] Shot schema as in Section 7.1: name, source, time, camera, size, crop, background, antialias, layers
- [x] Time of a shot: `steps` with `every`, `frozen` with a frame count, `keys`
- [x] Frame plan: for each frame, its step and the value of every track
- [x] Layer interface and registry: a layer takes the frame's data and values and adds actors to a plot
- [x] Docs: shot file reference (type, default and example per key)

**Branch 2: `phase2/scene-views`** (cameras and lights; needs branch 1)
- [x] View: perspective and parallel, flexflow's camera keys; `cameras.yml` views (Section 8.1)
- [x] Camera track between named views: linear and spline path, eased
- [x] `fit`: along a view's direction, far enough to show a box
- [x] `follow`: focal point on a body's centre at a station
- [x] Lights: default kit, `raking`, or a list
- [x] Projection of model points to the screen, with exact tests
- [x] Docs: cameras page

**Branch 3: `phase2/layers-flow`** (layers that draw the flow; needs branch 1)
- [x] `iso`: field, level, colour_by, range, colormap, opacity, wall_gap
- [x] `iso`: clip by a plane, `grow` along an axis, `grey`
- [x] `slice`: normal, position, field, range, fade_weak, mask near the wall
- [x] `body`: one named body, a list or all; colour, opacity, field and range on the surface, zero contour
- [x] Reveal look written as a shot file on these layers; `reveal.py` goes, its golden test stays
- [x] Docs: these layers, with an example on generated data

**Branch 4: `phase2/layers-markers`** (layers without flow data; needs branch 1)
- [x] `outline`: bounds from `domain`, `crop` or numbers; colour, width, opacity
- [x] `glyphs`: arrows on a face of the domain or at points
- [x] `markers3d`: `arrow3d`, `block`, `sphere`
- [x] `geometry`: a body from the geometry source, parameters as tracks, colour by its arrays
- [x] Docs: these layers, with an example on generated data

**Branch 5: `phase2/render-cache`** (rendering; needs branches 2, 3 and 4)
- [x] Backend choice: OSMesa when installed, else EGL; `backend` forces one
- [x] `scene.render_frame(shot, frame)` and `scene.render(shot, ...)`: a process per frame, `jobs`, threads per job
- [x] Frame keys (Section 11): frames are skipped unless their key changed; `force`
- [x] Frozen shots contour once and cache the surfaces
- [x] Draft size: `scale` and `size`, frames in `frames/<shot>@<W>x<H>/` (Section 7.5)
- [x] Memory of one frame measured, and the safe number of jobs
- [x] Tests on generated data; docs: rendering and caching

**Branch 6: `phase2/cli-shot`** (commands; needs branch 5)
- [x] `flowreel` entry point on shellkit: one-shot and interactive
- [x] `shot render` with `-j`, `--frames`, `--scale`, `--size`, `--backend`, `--force`
- [x] `shot preview` (`--every`, `--scale`) and `shot memory`
- [x] `shot template`: a commented shot file with the defaults
- [x] Help text; docs: commands page

**Branch 7: `phase2/golden-shots`** (the check; needs all the others)
- [x] Small domain data and a golden domain frame drawn by the prototype's `render_frozen.py`
- [x] Golden carving frame drawn by the prototype's `render_carve.py`
- [x] Shot files for the domain and carving shots; `examples/` shot on generated data
- [x] Image-difference tests of the three shots through `shot render`

Left out of Phase 2: the `pathlines` layer (no shot of the reference film uses it, and it
needs every step saved), `dimension3d` and `label3d` (they draw text, so they come with
Phase 4's text and Phase 6's anchored annotations), ambient occlusion, and `--slurm` and
`--submit` (Phase 5).

**Phase 2 is done when** the reveal, domain and carving shots, each rendered from a shot
file by `flowreel shot render`, match the golden frames. **Done 2026-11-17:** all three match
(`tests/test_golden_shots.py`): mean differences 0.08, 0.006 and 0.05 grey levels under
OSMesa, and a nearby frame of each fails the same limits.

### 19.3 Phase 2B tasks

Added 2026-11-13 for the studies after the film: long cylinders, pinned ends, cylinders
in tandem and bodies modelled by equations. It follows Phase 2 because it builds on
layers, views and rendering, and before Phase 3 because the panels there take bodies by
name. Branches 2, 3, 4 and 6 need only branch 1, so they can be built in parallel;
branch 5 needs branch 4. Branches 7 and 8, added 2026-11-18, need nothing of this phase
and can be built at any time before branch 9.

**Branch 1: `phase2b/bodies-declared`** (data model)
- [x] `Body` record (zone, axis, diameter, ends, series) and the `bodies:` schema of `flowreel.yml`
- [x] Body names resolved through `bodies:` (`zone`, default the name) for layers, `follow` and wall fields; one declared body may go unnamed (layers already take the source's zone names)
- [x] A body's centreline and diameter from the surface; `follow` takes `axis` from the declaration (the centre at a station is `framing.body_centre`, from Phase 2)
- [x] `project init` writes `bodies:` from the source's surface zones, supports left to fill
- [x] Docs: bodies page

**Branch 2: `phase2b/series-csv`** (time histories; needs branch 1)
- [x] CSV series: `file`, `time`, `columns`; `series(name, body=...)`
- [x] Histories at many points: `by` and `stations`; one file per node through `{node}` in `file` (Section 24, question 2)
- [x] OTHD and OISD readers refuse a file with more than one group
- [x] Tests on generated CSV files; docs, with the Analyzer commands that export them

**Branch 3: `phase2b/layers-supports`** (needs branch 1)
- [x] Support registry; `clamped` and `pinned`
- [x] `roller`, `spring`, `free`, `prescribed`; `tension`
- [x] `supports` layer: at the body's position per frame, sized in diameters, `min_pixels`
- [x] The domain shot's clamps drawn by `supports`; its golden frame still matches
- [x] Docs, with a picture of each symbol

**Branch 4: `phase2b/tracks-series`** (needs branch 1)
- [x] Series track: value at the frame's time, `column`, `scale`, `offset`; `station` for a history at many points
- [x] `centreline` layer from the surface: tube, colour by a value per station
- [x] `centreline` from probes; `amplify`, rest line, envelope
- [x] `amplify` on a `body` layer, refused in shots with flow layers
- [x] Tests with exact values; docs

**Branch 5: `phase2b/bodies-virtual`** (needs branch 4)
- [x] Virtual body in `bodies:`: `shape`, `params`, `attach`, `drive`
- [x] Shapes `pendulum`, `spring`, `mass`
- [x] `ghost` style; wall fields on a virtual body are an error
- [x] Docs, with an example on generated data

**Branch 6: `phase2b/long-span`** (needs branch 1)
- [x] Windowed PLT reading: nodes and cells of a box, only the asked variables, memory-mapped
- [x] Cached window index, with a margin for the body's motion
- [x] `crop: {around: ...}`, its station a track shared with the camera's `follow` (`follow` with a station track and `motion: false` is built in Phase 2)
- [x] `stretch` on a shot, with its note in the frame
- [x] `memory_per_step` of a windowed source (`shot memory` already prints it beside the measured peak); refusal of a shot that cannot fit, counting about 0.7 GB per job before any data
- [x] Frame keys and frozen surfaces include each data file's size and modification time (Section 24, question 3)
- [x] Docs: long bodies page

**Branch 7: `phase2b/geometry-grooves`** (geometry source; needs nothing of this phase)
- [x] `grooved_cylinder`: grooves in segments, `length`, `gap`, `stagger` (Section 5.3); segment ends rounded by `edge`
- [x] Carving and `cutters` with segments; the carving golden frame still matches
- [x] Tests on the surface (groove depth inside and outside segments, stagger between neighbours); docs and an example of staggered spanwise grooves

**Branch 8: `phase2b/layers-axes`** (layers; needs nothing of this phase)
- [x] Axis labels in Lato through VTK's font file, sized in pixels
- [x] `axes` layer, `style: triad`: a corner triad in its own viewport, turning with the camera
- [x] `style: arrows`: labelled arrows at a point or a body end, sized in model units or diameters
- [x] `style: ruled`: a box (`domain`, `crop` or numbers) with ticks and numbers, in the source unit or in diameters
- [x] Tests (projection of the triad and ticks, draft scaling); docs and an example

**Branch 9: `phase2b/bodies-check`** (needs branches 1 to 6)
- [x] Generated case, written at test time: a PLT with a cylinder 500 diameters long and a second body, a `flowreel.yml` with pin-roll supports and tension, CSV histories of the probes and of a pendulum
- [x] Shots of it: a travelling window, the whole span by `centreline`, the pendulum
- [x] Under `stretch`, support symbols, axes arrows and ticks keep their shape and labels go where the stretched model is drawn (found by the span shot)
- [x] Tests: the frames render, the window reads a small part of the file, the pendulum follows its series
- [x] `examples/` project on generated data

**Phase 2B is done when** those three shots render from the generated case and the
window shot's memory does not grow with the span. **Done 2026-11-18:** the travel, span
and pendulum shots render from the generated case (`tests/test_riser500.py`); a step
through the window costs 0.61 MB against 15.6 MB whole, and 0.61 MB in a case half as
long. Section 24 question 1 (a real run's file) stays open.

### 19.4 Phase 3 tasks

Added 2026-11-18. Phase 3 builds `compose`: layouts that tile frame folders, and the 2D
panels of Section 9.2, drawn per frame by matplotlib. Branches 1 and 2 need nothing of
this phase, so they can be built in parallel. Branches 3 and 4 need only branch 2 and
can also be built in parallel. Branch 5 needs branches 1 and 2, branch 6 needs branches
1 to 5, and branch 7 needs all of them.

**Branch 1: `phase3/compose-layout`** (data model and tiling)
- [x] Layout schema (Section 9.1): `size`, `background`, `tiles` with `frames`, `at` and `size`; errors name the file and key path
- [x] `grid: [rows, cols]` places tiles automatically, with a gap
- [x] Frames matched by index across tiles; a missing frame is an error unless `missing: hold`
- [x] `stations: {shot, at}`: one shot rendered at several stations of a long body (its crop and its camera's `follow`), each tile labelled with its station
- [x] `compose.layout(...)`: frames skipped unless their key changed (the tiles' files, sizes and modification times, the layout's settings); `force`
- [x] Docs: layouts page, with an example on generated frames

**Branch 2: `phase3/panels-core`** (panel interface and time plots)
- [x] Panel file: `type`, `size`, `times` (a shot's frame times, or a list), and one `style` block shared by all panels (Lato, maths font, colours, line widths)
- [x] Panel registry and the drawing loop: the figure is built once and moved along in time; drawn in parallel chunks, `jobs`
- [x] Panel cache (Section 11): key from the panel's settings, its times, the style and the files it reads
- [x] `series` panel: one or several series from `flowreel.yml` by body, lines to the current time ending at a dot at the interpolated value, shared time axis, labels and colours per entry
- [x] `phase` panel: one series against another, the trace to the current time and a dot
- [x] Tests with exact values (line ends, dot positions, times between samples); docs: panels page

**Branch 3: `phase3/panels-span`** (panels of a long body; needs branch 2)
- [x] `map` panel: a history at many points (`by`, `stations`) against span and time, filling in to the current time; colormap, range, colorbar, one or several bodies stacked
- [x] `locator` panel: a body's span as a bar, its shape now (amplified), its supports, and the windows on show (from the shots' crops at that frame)
- [x] Tests on generated histories; docs, with an example on the riser case

**Branch 4: `phase3/panels-flow`** (panels from flow data; needs branch 2)
- [x] Planar cut of a source's step: a triangulation and its fields (cut by a plane, at a body's station), read through the window when the source is long
- [x] `section` panel: a cut's field as contours, streamlines relative to the moving body, the body's outline, an inset that follows the body
- [x] `cuts` panel: the same cut at several stations side by side, labelled
- [x] `strip` panel: a body from one side coloured by a wall field, with its zero contour
- [x] Tests on generated data; docs

**Branch 5: `phase3/compose-rate`** (panels in a layout; needs branches 1 and 2)
- [x] Panel tiles in a layout: `panel: FILE`, drawn at the layout's frames
- [x] `rate: output` (Section 9.3): such a panel is drawn at given output times, between flow frames and held through given holds; `compose.layout` takes those times so the film build (Phase 4) can pass its freezes
- [x] Tests (a dot drawn between two flow frames lies between their values); docs

**Branch 6: `phase3/cli-compose`** (commands; needs branches 1 to 5)
- [x] `compose layout LAYOUT.yml` with `-o DIR`, `--force`, `--scale`
- [x] `compose panel PANEL.yml` with `-j N`, `-o DIR`, `--force`
- [x] Help text; docs: commands page

**Branch 7: `phase3/golden-compose`** (the check; needs all the others)
- [x] Small generated series of two cases and a golden comparison frame drawn by the prototype's `compose_compare.py` (two wake tiles and its plots)
- [x] Generated sectional lift of two cases and a golden lift-map frame drawn by the prototype's `render_extras.py liftmap`
- [x] Layout and panel files for both; image-difference tests through `compose layout` and `compose panel`, each with a nearby frame that must fail the same limits
- [x] `examples/` project on generated data

Left out of Phase 3: `compose plot` (Section 13 lists it, but nothing defines it beyond
`compose panel`), and the `data surface` and `data series` commands. The lift map's
golden test reads sectional lift as a CSV history at many points, so it does not need
`data surface`. The `section`, `cuts` and `strip` panels have no golden frame in this
phase; Phase 4's rebuilt AFMS film checks them.

**Phase 3 is done when** the comparison and lift-map frames, composed from files by
`flowreel compose`, match golden frames drawn by the prototype's own code. **Done
2026-11-19:** both match (`tests/test_golden_compose.py`, `docs/guide/composing/compose.md`): the
comparison pixel for pixel, the lift map within 0.001 grey levels on average, and a
nearby frame of each fails the same limits.

### 19.5 Phase 4 tasks

Added 2026-11-19. Phase 4 builds `film`: one `film.yml` turned into `film.mp4` (Section
10), with captions and 2D shapes (Section 12, the 2D part; 3D and anchored shapes are
Phase 6), cards, rates, freezes, holds, audio, a watermark and a preview copy, and the
`film` commands of Section 13. It replaces the prototype's `make_film.py` and
`film_text.toml`. Branch 1 comes first. Branches 2 and 3 need only branch 1 and not each
other, so they can be built in parallel. Branch 4 needs branches 1 to 3, branch 5 needs
4, branch 6 needs 5, and branch 7 needs all of them.

**Branch 1: `phase4/film-schema`** (data model and timeline)
- [x] `film.yml` schema (Section 10.1): `output`, `fps`, `size`, `style`, `audio`, `watermark`, `shots`; each shot one of `frames`, `layout`, `card` or `hold_last_of`, with `seconds`, `rate`, `freezes`, `fade`, `fade_out_at`, `text`; errors name the file and key path
- [x] Text files (Section 10.4): captions as lists of blocks (`lines`, `at`, `place`, `size`, `align`, `colour`, `box`, `shadow`, `shapes`, `id`), in the shot or in `text/` files; `include:` for any file (Section 15)
- [x] Timeline: each shot's planned length from its frame count and rate, its freezes and holds; caption times in the finished shot (freezes shift what follows); `end: {shot: NAME, at: S}` across a cut; frames, steps and seconds kept apart (Section 3)
- [x] Output positions of a shot (`compose.output_positions`) from its rate and freezes, for layouts with `rate: output` panels
- [x] Tests with exact values (lengths, caption times across freezes and cuts, positions); docs: film file page

**Branch 2: `phase4/film-text`** (captions, shapes and watermark, drawn; needs branch 1)
- [x] Caption drawing (Section 10.4): matplotlib with Lato and Lato maths, measured extents; places `top`, `bottom`, `centre`, `[x, y]`, `[centre, y]`; `align`; a soft shadow or a box; one transparent picture per caption
- [x] 2D shapes (Section 12): `arrow`, `line`, `box`, `circle`, `ellipse`, `bracket`, `dimension`, `highlight`, in pixels, in the caption's colour unless given
- [x] Watermark (Section 10.7): an image file or a line of text, `corner` or `place`, `size`, `opacity`; film level (drawn with the text, when `shots` or `seconds` say) and shot level (drawn into a shot's PNG frames, part of the frame key, scaled in drafts)
- [x] A golden caption picture drawn by the prototype's `make_film.caption_image` (a box, a shadow, arrows, maths), matched by FlowReel's, with a nearby caption that must fail; docs: captions and shapes page

**Branch 3: `phase4/film-cards`** (cards; needs branch 1)
- [x] Card file (Section 10.5): a background and blocks placed down the card: `image` (a file outside the repository), `title`, `divider`, `names` (a heading and a list), `text` (small print); sizes, colours and spacing in pixels
- [x] Card drawing with Pillow and the bundled Lato, centred by measured widths
- [x] A golden opening card drawn by the prototype's `make_film.opening_card` (its logo replaced by a generated image), matched by a card file; docs: cards page

**Branch 4: `phase4/film-clips`** (base and finished clips; needs branches 1 to 3)
- [x] ffmpeg: a standard build from conda-forge in `flexflow_env`, declared in a new `environment.yml` (pip cannot install ffmpeg, so not in `pyproject.toml`), with install notes in the README; found through `FFMPEG` or the path, its version and filters (`minterpolate`, `xfade`) checked once, with a clear error naming the binary found (the workstation's `ffmpeg` on the path is Tecplot's own copy)
- [x] Base clip of a frames shot: the frame order with freezes, `rate: {fps, to_output}` with `interpolate` (motion-compensated, scene cuts off), `repeat` and `blend`; encoded once, keyed by content (frame names and times, rate, freezes, filters; Section 11)
- [x] Base clip of a layout shot: its composed frames interpolated and its `rate: output` panels laid on at the output rate (Section 9.3), through `compose.layout(output=...)`
- [x] Base clips of cards and holds (`hold_last_of`: a shot's last frame, with or without its overlays)
- [x] Finished clip: fades on the picture, then captions, shapes and the film's watermark on top with their own fades, so text can sit on black; keyed by content
- [x] Tests on generated frames (lengths measured with ffprobe, a freeze's frames identical, caption times, keys that rebuild when a frame, a caption or a rate changes)

**Branch 5: `phase4/film-build`** (the film; needs branch 4)
- [x] Join the finished clips without re-encoding; planned and measured length per shot printed (Section 10.8)
- [x] Audio (Section 10.6): one or more tracks, each with `file`, `offset`, `start`, `volume`, `fade`; lengths measured from the files, a fade ending with the shorter of picture and track; `mute`
- [x] Preview copy: `preview: HEIGHT` writes `film_<H>p.mp4` from the same clips, scaled and encoded once, `crf`
- [x] `only`: one shot's finished clip, for checking its text
- [x] `film.srt` from the captions; `contact.png`: stills at captions, freezes or every few seconds, with text in place (`film check`)
- [x] Chapters (Section 10.9, added 2026-11-20): a shot's `chapter: TITLE` or `{title, at}`, checked against the shot's length; chapter times from the timeline; an ffmpeg metadata file given at the join (`-map_chapters`), in the film and its preview copy; `chapters.txt` with YouTube timestamps (`0:00 Title`)
- [x] Tests on a tiny generated film (Section 16: three shots of 10 frames, two captions, a freeze, a generated tone): lengths, caption timing, audio length, preview size, chapters read back with `ffprobe`, caches that rebuild when they should

**Branch 6: `phase4/cli-film`** (commands; needs branch 5)
- [x] `film build` with `--only SHOT`, `--mute`, `--force`, `--preview HEIGHT`, `--crf N`
- [x] `film check` with `--at caption|freeze|every:S`; `film lengths` (with each chapter's start and length); `film srt`; `film chapters` (prints `chapters.txt`)
- [x] `film template`: a commented `film.yml` with every key at its default
- [x] `project` context in the shell (Section 13), so film commands find `film.yml`
- [x] Help text; docs: commands page

**Branch 7: `phase4/golden-film`** (the check; needs all the others)
- [x] The AFMS film's own files written for FlowReel: `film.yml`, text and card files, its shot list and lengths taken from `make_film.py` and `film_text.toml` (no logo, music or data in this repository; the files that name them live with the research data)
- [x] A test that the film's planned shot lengths equal the prototype's `duration()` for the same shot list and frame counts, on generated frame folders of those counts
- [x] `examples/` film project on generated data, silent, with a card, a freeze, a layout shot with live plots and a watermark of text
- [x] The rebuild on the workstation from the real frames: lengths per shot measured against the prototype's film, and a contact sheet at every caption compared with the prototype's film at the same times; results written here

**Branch 8: `phase4/install-script`** (installing on a new machine; added 2026-11-21)
- [x] `install.sh`: finds conda, creates `flexflow_env` from `environment.yml` or adds only what an existing one lacks, installs shellkit if missing (`SHELLKIT_DIR` for a local checkout), FlowReel editable, checks ffmpeg, adds a `flowreel` alias; `--uninstall`, `-y`, `--no-alias`
- [x] Cards drawn in the film's `style.font` (any installed family, nearest weight), as captions and panels already are: the AFMS film's final version is in Times New Roman
- [x] Tried on airavata from a fresh clone (991 passed with VTK 9.7 and a raqm Pillow, after the fixes above), and the AFMS film built there from its files

Left out of Phase 4: 3D and anchored shapes (`arrow3d` ..., `{model: ..., view: ...}`
points; Phase 6 with the camera editor), ducking audio under narration (Section 10.6,
"later"), `compose plot`, and the `data` commands.

**Phase 4 is done when** the AFMS film is rebuilt from files, the same length, with its
captions in place. In this repository that is checked on generated frames of the same
counts (lengths against the prototype's own `duration()`, captions and the card against
pictures drawn by its own functions); the rebuild from the real frames is run on the
workstation and its result recorded under this line.

**Done 2026-11-21**, rebuilt on airavata (not the workstation: the frames are there) in
`studies/flowreel_video`, from files written by `tools/afms_film.py --prototype
../afms_video` (the final version: Times New Roman, STIX maths, moved captions), with
`afms_video`'s frames, series and assets linked in. `flowreel film build --preview 480
-j 16` took 9.5 minutes on the login node, at low priority.

- **Length.** Every shot's measured length equals its planned length and the
  prototype's `duration()`; the film is 131.88 s. The prototype's own film measures
  130.83 s: its five interpolated 8 fps shots each came out 0.21 s short (minterpolate
  drops the last flow frame, fixed in FlowReel's clips) and its domain shot was cut
  from 289 frames to 12.00 s. The music is 129.85 s, so both films end in silence.
- **Captions.** A still at the middle of each of the 32 captions, taken from FlowReel's
  finished clip and from the prototype's `clips/shot_<name>.mp4` at the same time in
  the shot, differs by at most 0.5 grey levels on average, with no pixel clearly
  different. The live plots match too.
- **Card.** Built first with Pillow's basic layout, the opening card differed by 3.6
  grey levels on average (1.9% of pixels): airavata's Pillow kerned the prototype's
  text (raqm). Kerning was kept (Arun, 2026-11-21): FlowReel kerns card text, tile
  labels and watermarks wherever Pillow has raqm, as the prototype's card was. Rebuilt
  so, the opening card is identical to the prototype's film (mean difference 0.00).

### 19.6 Phase 5 tasks

Added 2026-11-21. Phase 5 renders on a Slurm cluster: `shot render --slurm FILE` writes a
job script and `--submit` hands it to `sbatch`, so a long render runs on a compute node
without hand-written scripts (it replaces the prototype's `render_airavata.slurm`). The
first cluster is airavata's `node1` (128 cores, 125 GB, no GPU; off-screen drawing is
Mesa EGL on the CPU, as the prototype's renders were), which is shared with simulation
jobs. So a render asks for part of the node, sizes itself from what Slurm gave it, and
can be stopped and submitted again without redrawing a finished frame (frame keys,
Section 11).

Branch 1 comes first. Branch 2 needs nothing from branch 1, so the two can be built in
parallel. Branch 3 needs branches 1 and 2, branch 4 needs 3, and branch 5 needs all.

**Branch 1: `phase5/jobs-partitions`** (data model and job scripts)
- [x] Partition table (Section 14): `jobs/partitions.yml` in the package with airavata's `part1` (3 h), `part2` (24 h), `part3` (72 h) on `node1` (128 CPUs, 125 GB), and Param Shakti's from flexflow's `hpc_partition.py`; a user file (`~/.flowreel/partitions.yml`) adds or overrides clusters; the cluster from `--cluster`, `FLOWREEL_CLUSTER`, or the host name
- [x] Job spec: partition, CPUs, memory, time, array and its concurrency (`%N`), dependencies, output log; checked against the partition (CPUs, memory, walltime), errors naming the limit
- [x] Job script writer: `#SBATCH` lines, the environment (the `flowreel` of the environment it was written from, `unset DISPLAY`, the backend), the command; plain text that reads as a person would write it
- [x] Tests with exact script text; docs: Slurm page (partitions and scripts)

**Branch 2: `phase5/jobs-resources`** (what a job has; independent of branch 1)
- [x] Cores and memory of the running process: in a Slurm job its allocation (`SLURM_CPUS_PER_TASK`, `SLURM_MEM_PER_NODE`, the cgroup's limit, the CPU affinity), elsewhere the machine's free memory and cores; used by `default_threads`, `check_fits` and `shot memory`'s suggested `-j`
- [x] Off-screen check: draw a tiny scene with each backend and report which work and how fast (`flowreel jobs check`), run first in every job script so a node without OpenGL fails in seconds, not after loading data
- [x] Tests with a faked environment and cgroup files; docs

**Branch 3: `phase5/jobs-plan`** (splitting a render; needs branches 1 and 2)
- [x] Sizing: from `shot memory`'s measured peak (kept in the output folder) choose CPUs, memory, `-j` and threads per task within the partition and the memory asked for; without a measurement, a first task measures, then the rest run
- [x] Split a shot's frames into array tasks of consecutive frames (a frozen shot's surfaces are cached, Section 11), with `--max-running N` so a render takes part of the node; time per task estimated from the measured seconds per frame, with a warning when it nears the walltime
- [x] Resume: frames already drawn with their key are skipped, so a cancelled or timed-out render is submitted again as it is; `--missing` submits only tasks with frames still to draw
- [x] Tests on generated shots (task ranges, sizes, resume); docs

**Branch 4: `phase5/cli-slurm`** (commands; needs branch 3)
- [x] `shot render --slurm FILE` and `--submit`, with `--cluster`, `--partition`, `--time`, `--mem`, `--cpus`, `--max-running N`, `--after JOBID`, `--missing`; prints the job id and the log path
- [x] `compose layout`, `compose panel` and `film build` take `--slurm FILE`, `--submit` and `--after JOBID`, so a film is a chain of jobs: renders, then composes, then the build
- [x] `jobs partitions` (the table), `jobs check` (branch 2), `jobs status [JOBID]` (Slurm's state of FlowReel's jobs and the frames drawn so far)
- [x] Help text; docs: commands page

**Branch 5: `phase5/golden-slurm`** (the check; needs all the others)
- [x] A fake `sbatch` and `squeue` on the path in tests (they record the call and run the script, array tasks one by one): a generated shot submitted, rendered, cancelled half way and resubmitted with nothing redrawn
- [x] The AFMS reveal written as a FlowReel shot for the real bare case (in the AFMS project folder on airavata, outside this repository)
- [x] `examples/` Slurm project on generated data, with the fake `sbatch` so it runs anywhere
- [x] On airavata: `flowreel shot render reveal.yml --submit` on `node1`, its frames compared with the prototype's `frames/bare_reveal` by image difference, time and memory per frame recorded here

Left out of Phase 5: GPU rendering (airavata has no GPU), MPI or multi-node renders (one
frame is one process), and queue systems other than Slurm.

**Phase 5 is done when** `flowreel shot render --submit` renders the AFMS reveal on
airavata, matching the prototype's frames. In this repository that is checked with a fake
`sbatch`; the run on `node1` waits for a time it is free of simulation jobs, and its
result is recorded under this line.

**Done 2026-11-21** on airavata. In `studies/flowreel_video/reveal/`, written by
`tools/afms_film.py --reveal CASE` (the shot from the prototype's `render_frames.py`,
`flowreel.yml` by `project init`), one command, `flowreel shot render bare_reveal.yml
--submit --cpus 32`, from the login node:

- **Job 1307, the measuring job** (4 cores, 16 GB, `part1`; 43 s): the off-screen check
  (EGL works; OSMesa is not installed), frame 0 measured inside the job's allocation
  (peak 1.27 GB, 25 s on 4 threads), then the render planned and submitted from
  `node1`: 121 frames in one task of 32 cores, 51 GB, `-j 32`, 20 minutes.
- **Job 1308, the render**: 121 frames drawn in 2 min 24 s (32 s a frame on one thread,
  32 at once, peak 1.37 GB a frame).
- **Against the prototype's `frames/bare_reveal`**: all 121 frames within the golden
  limits; mean difference median 0.045 grey levels (worst 0.070, frame 58), clearly
  different pixels at most 0.0023% (frame 84).
- The first plan's time was generous (20 minutes asked, 2.4 used): one frame measured
  on 4 threads was scaled to one thread as four times slower, and it was the frame that
  also opens the data. The render's own record (32 s a frame over 121 frames, on one
  thread) now sizes the next one.

### 19.7 Phase 6 tasks

Added 2026-11-22. Phase 6 makes cameras something picked by eye, not typed: a window that
shows a shot's scene and collects views into `cameras.yml` (Section 8.3), the camera
commands of Section 8.2, and captions and shapes anchored to model points, projected per
frame so an arrow follows a moving camera (Section 12). `film srt` was built in Phase 4;
an anchored caption is still plain text in the `.srt`, so nothing is left of
it here.

Branches 1 and 2 need nothing from each other, so they can be built in parallel.
Branch 3 needs both (the editor writes through branch 1 and shows branch 2's anchors),
branch 4 needs 3, and branch 5 needs all.

**Branch 1: `phase6/cameras-file`** (camera data model and the commands' library)
- [x] Writing `cameras.yml`: views and tracks saved in the layout of Section 8.1 (one view
  a line, tracks with their keys), read back equal by `load_views` and `load_tracks`; a
  `.bak` of the file it replaces; comments are not kept, and the file's first line says so
- [x] Easing per segment: `ease` on a track key sets the segment after it (the track's
  `ease` stays the default); `camera_path.build_track(...)`, a track from keys with easing
  per segment, and `update_cameras`, which adds it to a file, for `camera path`
- [x] Orbit: an arc of keys round a target (a point, or a body's centre at a station
  along its axis) with radius, elevation from and to, azimuth span, lead and frame count,
  for `camera orbit`
- [x] Import: a view from a ParaView state (`.pvsm` XML and `.py` trace) and from a
  flexflow `cam.yml`, for `camera import`
- [x] Tests on generated files (round trip, segment easing, orbit geometry, small
  ParaView states written in the test); docs: `docs/guide/shots/cameras.md`

**Branch 2: `phase6/annotations-anchored`** (independent of branch 1)

A film shot names a folder of frames, not the shot file that drew them, so `shot render`
records the camera of every frame it draws; an anchor then takes the camera that drew
the frame on screen, whatever moved it (a track, `follow`, `fit`), with nothing to
repeat in the caption.

- [x] `shot render` records each frame's view, picture size and stretch in the frames
  folder (`.views.json`, beside `.keys.json`), for drawn and skipped frames alike
- [x] Anchored points: `{model: [x, y, z]}`, with `offset: [dx, dy]`, in a shape's points
  and a caption's `place`; resolved per output frame of the finished shot from the frame
  shown (rates and freezes, Section 10.2: between two frames the positions are blended),
  its recorded view and size, fitted to the film's size as the picture is; optional
  `view: V` or `track: T` from the project's `cameras.yml` (at its root, Section 24
  question 6; else beside the film file) for frames FlowReel did not draw. An anchored caption is drawn once per output frame it shows in; errors for a
  card or layout shot, and for frames with no record and no `view` or `track`
- [x] A point behind the camera or off the frame hides its shape (or its caption's text)
  for that frame; `film check` warns with the caption and the times
- [x] `label3d` (text at a model point) and `dimension3d` (between two model points, with
  a value) as caption shapes, projected and drawn in 2D like the others, and `label`
  (text at a pixel point), the 2D shape they become
- [x] Draft sizes: anchors follow frames drawn with `--scale` (their recorded size) and
  `film build --preview` (scaled from the film); tests on a generated film (an arrow on a
  camera track, checked against `project()`); docs: `docs/guide/film/captions.md`

**Branch 3: `phase6/camera-editor`** (needs branches 1 and 2)
- [x] Editor state without a window: views collected with their frames; save, undo,
  replace the nearest, play, next step; the file written (branch 1) after every change,
  so closing the window loses nothing
- [x] The window (a VTK interactor): keys `s`, `u`, `r`, `p`, `n` and buttons for them;
  *Frame* and *Time step* sliders; on screen the views saved, the frame and the step;
  each step's scene built once (the shot's layers, as `shot render` builds them)
- [x] `--vtp DIR`: open saved surfaces instead of the data; `shot render --save-vtp`
  writes a frame's surfaces to copy to a machine with a display
- [x] The shot's anchored points (branch 2) drawn as markers with their names
- [x] Tests: the state with fake views; the window off-screen driven by synthetic key
  events; docs: camera editor page

**Branch 4: `phase6/cli-camera`** (commands; needs branch 3)
- [x] `camera edit SHOT.yml` (`--track NAME`, `--frames N`, `--vtp DIR`, `--film FILE` for
  the captions' points, `-c FILE`: every camera command reads and writes one `cameras.yml`)
- [x] `camera path`, `camera orbit`, `camera import`, `camera project` (`--view V` or
  `--track T`, `--points ...`, `--size W H`), `camera preview TRACK` (small frames of a
  track over saved surfaces or the shot's first step)
- [x] The `view` context in the shell (`use view:main`, Section 13)
- [x] Help text; docs: commands page

**Branch 5: `phase6/golden-camera`** (the check; needs all the others)
- [x] A scripted editor session (off-screen, synthetic keys) on a generated shot picks
  views into a new track; `shot render` draws it; frames compared with golden frames
- [x] A golden caption frame: an anchored arrow on a camera track, at three frames
- [x] `examples/camera_editor` on generated data, with the scripted session so it runs
  anywhere (made in branch 3; here it also renders the picked track)
- [x] By hand on a display: a track picked in the window on the laptop (surfaces copied
  with `--vtp`), rendered, and recorded here

Left out of Phase 6: editing a track's keys by dragging on a timeline, and picking points
in the window for anchors (anchors are typed; the window shows where they land).

Asked for after the run by hand, moved to Phase 8 (Section 19.9):
- Mark the frames that have a saved key on the Frame slider (ticks or numbers in another
  colour), so the keys of a track can be seen without playing it.
- Let the Frame slider move the Time step slider to the step that frame shows (through
  the shot's `time` keys), so the two need not be set apart; the Time step slider stays
  for looking at other steps while framing a view.

**Phase 6 is done when** a new camera track is picked in the window and rendered.

**Done 2026-11-22.** Arun picked a track by hand in the window on the laptop
(`examples/camera_editor/run.py --window`): keys saved with `s`, the sliders and Play
behaved; the track was rendered. The scripted check of the same path is
`tests/test_golden_camera.py`.

### 19.8 Phase 7 tasks

Added 2026-11-22, while Phase 6 is being built. Phase 7 turns the per-phase pages in
`docs/` into documentation a new user can start from: a tutorial that makes a short film
from a public data set, a user guide, and a reference generated from the code where it
can be, so it cannot drift. It needed three answers, all given on 2026-11-22 (Section 23):
how a project folder is made and laid out (Section 24, question 6, kept until now for
this phase), which public data set the tutorial uses (question 7: pyvista's
`cylinder_crossflow`), and how the documentation is presented (question 8: a website).

**Presentation** (question 8): the whole of `docs/` becomes one MkDocs Material website on
GitHub Pages, in three parts: the Tutorial, the User guide (today's per-phase pages, in
reading order) and the Reference; `PLAN.md` stays out of it. The pages stay Markdown in
`docs/`, so they still read on GitHub, only without the site's tabs and notes. The site
is built with `mkdocs build --strict` on every PR, so a broken link or a page missing
from the navigation fails the PR, and deployed on every push to `main`. A website was
chosen over pages read on GitHub for search and navigation across some thirty pages,
which a new user needs more than an expert. The tutorial is one page per chapter under
`docs/tutorial/`, each ending with a still to compare, and its first page shows a short
GIF of the finished film; the stills and the GIF are rendered from `cylinder_crossflow` by
a script, and committed only once branch 2 has recorded that its licence allows it.

**Project rules** (question 6): `flowreel.yml` stays the visible project file, for what
is edited by hand, and a hidden `.flowreel/` folder holds only machine state (caches,
measured timings). `project init` makes the folders `shots/`, `text/`, `cards/`,
`assets/` and `data/`, with `film.yml` and `cameras.yml` at the root, and a `.gitignore`
for `frames/`, `clips/`, `.flowreel/` and `data/`; `init --link` puts a symlink to the
data in `data/`, which is never copied. Generated output goes under the project root
wherever a command is run from (`-o` still overrides). One `cameras.yml`, at the root,
serves every shot and caption; one left beside a shot file is an error that says to
move it. Outside a project the commands stop with an error saying how to make one,
except `project init`, the `template` commands and `jobs`; the Python library works
anywhere. Paths written in files stay relative to the file.

The data set is one steady step of a 2D flow at Re 35, where the wake stays attached and
does not shed. So the tutorial's film is made with what FlowReel does to one step:
camera moves, a field coloured and its range swept, contour lines and the wall, rather
than a wake that develops in time. The 2D mesh is given a thin span when it is converted,
so the layers, which expect cells with volume, work on it unchanged.

Branches 1, 2 and 3 need nothing from each other, so they can be built in parallel.
Branch 4 needs all three (the tutorial uses the project rules and the data, and is pages
of the site), branch 5 needs branches 1 and 3 (the reference describes the project rules,
and is part of the site), and branch 6 needs all. Phase 7 starts after
Phase 6 is done, since the tutorial picks a camera in the editor.

**Branch 1: `phase7/project-rules`** (the project folder; question 6 decided)
- [x] Question 6, decided and confirmed 2026-11-22 (Section 24), recorded in Section 23
- [x] `project init` writes the agreed folders, `.gitignore` and (with `--link`) the data
  link; commands find the project by walking up, and stop outside one with an error
  saying how to make one (except `project init`, the `template` commands and `jobs`)
- [x] Generated output under the project root, wherever a command runs (`frames/`,
  `clips/`; caches and measured timings in `.flowreel/`); `-o` still overrides
- [x] One `cameras.yml` at the project root for shots (today beside the shot file) and
  captions; a `cameras.yml` beside a shot file is an error that says to move it
- [x] `project info` (source, bodies, shots, cameras, film, caches and their sizes) and
  `project clean` (`--frames`, `--cache`, `--clips`, `--dry-run`), Section 13
- [x] Tests on generated projects; help text; docs: project page
- [x] `docs/guide/projects/rules.md`: every rule FlowReel imposes on a project in one page, each with
  its reason, what happens when it is broken and a link to the details; a new rule goes
  there in the same PR (`.claude/rules/documentation.md`)

**Branch 2: `phase7/tutorial-data`** (pyvista's `cylinder_crossflow`; independent of
branch 1)
- [x] The data set's licence and source checked and recorded (where pyvista's copy
  comes from, who made it, whether it may be shown in a film); if it may not, back to
  question 7. Checked 2026-11-22: it may (Section 24, question 7)
- [x] `examples/tutorial/get_data.py`: downloads `cylinder_crossflow` into the project's
  data folder (from `pyvista/data` at a fixed commit rather than with pyvista's
  downloader, which follows the latest copy and keeps it in its own cache), checks its SHA-256, and converts the EnSight case to
  a `.pvd` of one `.vtu` step: `fluid` extruded to a thin span (one cell, about 0.1 D) as
  the flow, with `velocity` split into `U`, `V`, `W` and `pressure` as `p`, and
  `wall_cylinder` extruded the same way as the body `cylinder`; it writes the licence and
  citation beside it, and a second run downloads nothing
- [x] A generated stand-in with the same names, fields and steps at a small size, so
  the tutorial's test runs without the network
- [x] Tests (checksum refused, conversion of the stand-in, rerun skips); docs: the data
  set, its source, licence and how to cite it

**Branch 3: `phase7/docs-site`** (the website; independent of branches 1 and 2)
- [x] Question 8, decided 2026-11-22 (Section 24), recorded in Section 23
- [x] `mkdocs.yml`: the Material theme, search, tabs, notes (admonitions) and copy
  buttons on code; navigation in three parts, Tutorial, User guide and Reference, with
  `PLAN.md` left out; a `docs` extra in `pyproject.toml` (`mkdocs-material`, pinned)
- [x] Every existing page builds under `--strict`: broken links and anchors fixed, every
  page in the navigation; the pages still read on GitHub
- [x] `.github/workflows/docs.yml`: `mkdocs build --strict` on every PR, deployed to GitHub
  Pages on every push to `main` (Pages turned on in the repository's settings by Arun)
- [x] A test that builds the site strictly when `mkdocs` is installed (skipped otherwise);
  docs: building the site locally, and where it is published

**Branch 4: `phase7/tutorial`** (the tutorial; needs branches 1, 2 and 3)
- [x] `project init --body NAME=FILE` (once per body), so a `vtk` body gets its name
  (`cylinder`) rather than `body`; a single `--body FILE` is unchanged
- [x] A slice's `range` is a vector track, so a shot can sweep it (the plane is coloured
  afresh every frame); `iso` and `body` keep a fixed range
- [x] `project info` writes a shot's source with its body files on one line
- [x] `docs/tutorial/`, one page per chapter with an index page, each chapter ending with
  a still to compare: install; `project init` on the data; a first shot (`shot template`, the flow
  coloured by vorticity from velocity, contour lines of pressure, the cylinder; `shot
  preview`); a camera picked in the editor that moves from the whole domain to the
  cylinder; a second shot sweeping the colour range; a panel of the pressure
  coefficient round the wall; `film.yml` with a title card, two captions (one with maths, one
  anchored to the body), a freeze and silence; `film check`; `film build --preview`, then
  the full build; optionally Slurm. Done 2026-11-23, with two changes found while writing
  it: the pressure is shown by the panel's filled contours, since a shot has no layer of
  contour lines (a Phase 8 task, Section 19.9); and the panel draws the pressure `p`, not
  its coefficient, since the data set does not give its density. The tutorial's body
  needs `axis: z` and `diameter: 1.0` in `flowreel.yml`: a slab 0.1 long has no long
  axis to measure, and the cylinder's ends are capped in `get_data.py` so a camera
  looking along it sees a solid body
- [x] `examples/tutorial/stills.py`: renders each chapter's still and a short, small GIF
  of the finished film from `cylinder_crossflow` into `docs/tutorials/steady/images/`; committed
  only once branch 2 has recorded that the licence allows it; the GIF on the index page
- [x] `examples/tutorial/`: every file the tutorial writes, as it stands at the end, so a
  reader can compare theirs
- [x] A test that follows the tutorial on the stand-in data at a small size, command by
  command, and checks the film is 20 s with the captions in place

**Branch 5: `phase7/docs-reference`** (the guide and reference; needs branches 1 and 3)
- [x] `docs/index.md`, the site's first page: where to start (the tutorial), the user
  guide and the reference; the per-phase pages renamed as guide chapters, in reading order
  in the site's navigation
- [x] YAML reference: every key of every file type (shot, cameras, layout, panel, film,
  card, `flowreel.yml`) with type, default and example, generated from the schema modules
  and the `template` commands, with a test that fails when the page is out of date. Done
  2026-11-23: the keys come from the lists the code checks each file against, and each
  key's type, default and meaning from its row in the guide page, so a key the code
  accepts without a row in the guide fails the test too (ten rows were added to the
  guide, for keys only its prose had named)
- [x] Command reference generated from the help text, with the same test
- [x] `README.md` brought up to date (status, what it does, a still, install, links to
  the site and its tutorial); a docstring check over public modules (`.claude/rules/documentation.md`)

**Branch 6: `phase7/tutorial-check`** (the check; needs all the others)
- [ ] The tutorial followed on the published site, from a clean checkout on a machine
  that has never had FlowReel, with the real data set, by the instructions alone; time per chapter and every
  place where the reader stopped recorded here
- [ ] Fixes from that run, each a commit naming the chapter
- [ ] By a new user: someone other than Arun makes a 20 s film from the tutorial; what
  they made and what they asked recorded here

Rehearsal, 2026-11-23 (not the run above: done by Claude, who knows FlowReel, on
airavata). A clean clone of main into a new environment, `flowreel_rehearsal`
(`CONDA_ENV_NAME=... ./install.sh -y --no-alias`, so Arun's `flexflow_env` and shell
were left alone): VTK 9.7.2 and pyvista 0.49.2 from conda-forge, the versions a new
user gets. Real data; chapter 4 by its no-display route; the full-size renders on node1
through `srun`. Computer time, reading left out: install 45 s; chapter 2, 65 s with the
download; chapters 3 to 6, 8 to 21 s each; chapter 7, 2 min of rendering at -j 4 and
24 s of `film check`; the build 4 s; the chain of chapter 8 on Slurm, under 2 min. The
film came out at 20.00 s. What a reader would have stopped at, each fixed in a commit
on this branch naming its chapter:

- chapter 2: `project init`'s view `main` left the domain at 40% of the picture's
  width; `project info` printed `source: none` and a film shot with no frames, where the
  page said otherwise
- chapter 3: two lines of VTK-m warning on every frame (conda-forge's VTK 9.7); the
  page's picture was drawn from chapter 4's track, not from `main`
- chapter 4: `--save-vtp` warned of a bad X server connection
- chapter 7: matplotlib warned twice that it had no 'cursive' font
- chapters 7 and 8: the pages said `film check` builds every clip; it builds those with
  a caption, so the title's clip is built by the first `film build`
- chapter 8: the render jobs stopped in 3 s, sized from the measured 0.63 GB a frame
  but checked inside the job by the source's estimate of 0.7 GB; `jobs status` counted
  a starting task twice and printed Slurm's fields raw

Left out of Phase 7: translations, video tutorials, and a reference of the Python
library generated from its docstrings (the site documents the commands and YAML files).

**Phase 7 is done when** a new user makes a 20 s film from the tutorial.

### 19.9 Phase 8 tasks

Added 2026-11-22. Phase 8 collects the improvements Arun asks for while using FlowReel,
starting with the camera editor after Phase 6's run by hand. It comes after Phase 7, so
each change also updates the tutorial and the reference pages. The list grows as requests
come in; it is split into stacked branches by kind of feature (`phase8/<kind>-<topic>`)
when the work starts.

The tasks below were listed as they were asked for (2026-11-22 and 2026-11-23) and split
into branches on 2026-11-23. Each branch is stacked on the one before it; none needs
another's code, but each regenerates the reference pages, so they go in this order: the
checks first, so every later branch is tested on old and new VTK; then the two gaps the
tutorial met; then the rest.

**Branch 1: `phase8/ci-tests`**
- [x] A workflow that runs `pytest` on every PR and push to main, on Python 3.12, in two
  jobs: the oldest versions FlowReel declares (`vtk`, `pyvista` and the rest at their
  minimums) and the newest; OSMesa from the runner's packages for off-screen drawing,
  ffmpeg from them too; the reference-image tests run, not skipped
- [x] Whatever the oldest job finds: fixed, or the minimum raised in `pyproject.toml` and
  `environment.yml` with the reason in the commit
- [x] The README says how the tests run, and where CI runs them

**Branch 2: `phase8/checks-doctor`**
- [x] The versions CI tests (oldest and newest VTK and pyvista) kept in one place in the
  code, read by the doctor and by the CI workflow's test that the two agree
- [x] `flowreel doctor`: Python, FlowReel, VTK, pyvista, matplotlib, ffmpeg (version and
  filters), each said tested or not; the off-screen back ends (`jobs check`); the
  bundled fonts; and, inside a project, its root and what `project info` says; exit
  status 1 when something FlowReel needs is missing
- [x] Help, docs (commands page, a line in the install chapter of the tutorial), the
  reference regenerated

**Branch 3: `phase8/shots-fit`**
- [x] `camera: {fit: ...}` fits the box to the shot's picture (`fit(..., aspect=)`), the
  shot's size passed to the camera; a new key `shape: picture` (default) or `sphere`
  (the old fit, safe for any turn of the camera)
- [x] The shots that use `fit` checked: no test shot taken from the prototype does (their
  golden frames stay as they are); the shot commands example, whose `margin: 0.9`
  tightened the sphere, now fills the picture with `margin: 1.05`
- [x] Docs (cameras page, the YAML reference) and the shot template

**Branch 4: `phase8/layers-contour`**
- [x] A `contour` layer: lines of a field at `levels` (a list, or `{count, range}`) on a
  slice (`normal`, `position`, as the slice layer), in one `colour` or coloured by the
  field with a `colormap`, `width` in pixels; levels and range may be tracks
- [x] Tests on generated data: the lines lie on the slice at the asked values, and a
  frame draws them
- [x] Docs (flow layers page, the YAML reference, the shot template), an example, and a
  "Try" in chapter 6 of the tutorial: the pressure's contour lines over the sweep shot

**Branch 5: `phase8/layers-streamlines`**
- [x] A `streamlines` layer: seeds on a `line` (two points and a count), a `plane` (a
  rectangle and counts) or `round` a body (a ring at a station); traced in the frame's
  velocity both ways to a length; drawn as `lines` or `tubes`, in one colour or coloured
  by a field
- [x] `relative: true`: traced in the velocity relative to a moving body, as the section
  panel's streamlines are
- [x] Tests on generated data (a uniform flow gives straight lines along it; a vortex
  gives closed loops), docs, the YAML reference, the template and an example

**Branch 6: `phase8/project-reference`**
- [x] `reference: {rho, u_inf, length}` in `flowreel.yml`, each optional and positive,
  read with the project; an unknown key is an error, as everywhere
- [x] Layers and panels that take `params: {rho, u_inf}` use the project's values when
  they give none (a value given in the panel still wins; a shot's layer has no
  `params`); `length` is the unit of the axes layer's `unit: diameters` when it names no
  body (panels show no lengths in diameters)
- [x] Docs (the project page, the fields page, the YAML reference), the rules page if it
  makes a new rule, and an example

**Branch 7: `phase8/film-watch`**
- [x] `film build --watch`: build, then build again each time the film file, a card, a
  text file or a frame folder it uses changes (polled, no new dependency), until
  Ctrl-C; a build that fails says why and waits for the next change
- [x] Tests (a change to a caption builds again, only that shot's clip is made), help,
  the build page and the reference

**Branch 8: `phase8/editor-slider`**
- [x] Ticks on the *Frame* slider at the frames with a saved key, redrawn when a key is
  saved, replaced or undone
- [x] Moving the *Frame* slider moves the *Time step* slider to the step that frame shows;
  the *Time step* slider still moves alone
- [x] Tests (the editor's state, without a window), the camera editor page

**Branch 9: `phase8/sources-plt`** (added 2026-11-23, asked by Arun: FlowReel reads PLT
files without depending on FlexFlow, and takes time series from CSV; Section 24, q. 10)
- [x] The adapter that reads Tecplot binary PLT files is called `plt`: `plt:CASE` in a
  shot, `{adapter: plt, path: ...}`, `project init plt:CASE`; its code moves to
  `flowreel.sources.plt` and its class to `PltSource`. `flexflow` stays as a second name
  of the same adapter, so the shots written so far (the AFMS film's) keep working, and
  the old import path keeps working too
- [x] A case is a folder of `<name>.<step>.plt` files (in it, or in `binary/`), whatever
  wrote them; the adapter's errors and docs name the files it wants, not the solver
- [x] Time series come from CSV files declared under a body in `flowreel.yml`
  ([bodies](../docs/guide/projects/bodies.md#series)), the documented way for every source; the reading of
  FlexFlow's `.othd` and `.oisd` files stays as it is (Section 23, Data formats; one
  body only, Section 24, q. 4), described as a quick look at a FlexFlow case, not as the
  way
- [x] Docs: the sources page (`plt` first; `flexflow` as its other name), the commands
  and project pages, the YAML and command references, the examples (`plt:` in place of
  `flexflow:`); `project info` prints the source as `plt:`

**Branch 10: `phase8/tutorial-unsteady`**
- [x] A public unsteady data set of vortex shedding whose licence allows it to be shown
  (as `cylinder_crossflow`'s does); if none is found, ask Arun before using generated
  data instead. Chosen by Arun 2026-11-24: Boudina's "Numerical simulation data of a
  two-dimensional flow around a fixed circular cylinder" (Zenodo record 5039610, DOI
  10.5281/zenodo.5039610, CC BY 4.0; Polytechnique Montréal, solver Cadyf, Re = 100).
  `fixed_cylinder_atRe100` (1.17 GB, MD5 `fb3135ad...`) is text: `Re Ur`, `Nt N`, then
  per step its time and N lines `x y U V p`; 201 steps from t = 400 to 500, 82,872
  nodes, no elements. `Re100_fixe00.reactions` (329 kB, MD5 `9eeb693d...`): `t Fx Fy
  Mz` on the cylinder, t = 0 to 500. The data script downloads both with their
  checksums, triangulates the nodes (the cylinder's inside left out), gives the 2D mesh
  a span as the first tutorial's does, writes each step as a PLT file, and writes the
  force as the body's CSV series
- [x] A second tutorial, its own pages under `docs/tutorial/`: time tracks, a freeze on a
  moving flow, and a render of many steps as a Slurm job array; its data script and
  its project under `examples/`, tested by following it as the first one is
- [x] Its flow is read as PLT files with `plt:`, and the body's time history (its
  displacement, or the force on it) from a CSV file declared in `flowreel.yml`, drawn
  in a panel beside the shot
- [x] The first tutorial names `plt:` beside `vtk:` where it lists the sources a project
  can read (chapters 2 and 8)

**Branch 11: `phase8/docs-organise`** (added 2026-11-24, asked by Arun: the Markdown
files organised)
- [x] The plan out of `docs/`: `plan/` at the repository's root, one file a part
  (`design.md`, `phases.md`, `decisions.md`, `questions.md`), each section keeping its
  number, and `plan/README.md` saying which file holds which; every reference to
  `docs/PLAN.md` rewritten to the file that holds its section
- [x] The tutorials side by side: `docs/tutorials/steady/` (the first) and
  `docs/tutorials/unsteady/`, under `docs/tutorials/index.md`
- [x] The user guide in folders by part, as the site's navigation groups it:
  `docs/guide/projects/`, `shots/`, `rendering/`, `composing/`, `film/`, with
  `commands.md` and the worked example in `docs/guide/`; every link, the commands' help,
  the reference generator and the tests follow

**Branch 12: `phase8/series-sections`** (added 2026-11-24, asked by Arun: the AFMS film
made from the cases alone needs each case's sectional lift along the span; moved to
Phase 9 the same day, see below)
- [x] Moved: a body's sectional force along its axis, step by step from the flow, as a
  series, is Phase 9's `data extract sections` (Section 19.10, branch 4). It was first
  written as `project sections` (PR #84, closed unmerged) and checked on the AFMS smooth
  case: the span's mean C_L 0.788 and C_D 1.868 against the solver's 0.7877 and 1.8683

Branches are stacked in the order above. Branches 4 to 9 do not use each other's code;
they could be done by agents in parallel, but each one regenerates the reference pages,
so they are done one after another.

**Phase 8 is done when** every task listed here is done and Arun closes the list.

### 19.10 Phase 9 tasks

Added 2026-11-24, asked by Arun and settled in six rounds of questions the same day
(Section 24, question 11). A project's data comes in by **tag**: each case under
`data/<tag>/`, linked (or copied with `--copy`), with its own `domain.yml` holding its
bodies, units and series, so one project may hold several cases whose zones share names
(the AFMS film's two cylinders are both `cyl`). Shots name a tag. No project uses the
old layout yet, so it is replaced, not kept: `flowreel.yml` no longer declares bodies or
reference values, and `source: adapter:path` goes.

The layout:

```text
data/
├── bare/                      a tag: one case
│   ├── domain.yml             written by data import, edited by hand
│   ├── plt/    -> the folder the case's PLT files are in   (a link)
│   ├── othd/   -> its othd_files/;  oisd/ -> its oisd_files/
│   └── series/                written: motion.csv, force.csv, sections.csv ...
└── carve/                     a tag of kind geometry: domain.yml only
```

The decisions, for every branch:

- **Tags.** Letters, digits, `-` and `_`; unique in the project; no dots, since a body
  across tags is written `tag.body` (`bare.cyl`). One tag is one case, and may hold
  several kinds (`plt` or `vtk`, `othd`, `oisd`, `series`); `geometry` tags hold bodies
  made in code. A second import of a kind the tag has is refused unless `--force`, which
  replaces the link and keeps what was edited in `domain.yml`.
- **`domain.yml`** is written by `data import` with what it measured (kind, steps and
  times, zones, fields, bounds, each body's axis and diameter) and, commented, what only
  the user knows (units, supports); later imports add to it and never overwrite edits. It
  holds `units: {rho, mu, u_inf, length}` (so two cases may differ, and extracts need no
  `--param`), and `bodies:`, each with its zone (or file, for VTK; or function and
  parameters, for geometry), axis, diameter, ends and its `series:` (paths within the
  tag folder).
- **`flowreel.yml`** marks the project's root and holds what is the project's own:
  `defaults:` (back end, style) and, optionally, `tags:` for checks.
- **Shots** name a tag: `source: bare`, or `{tag: bare, kind: vtk, margin: 1.0}` with
  reading options. Within a shot a body is named as its tag names it (`body: cyl`);
  where tags meet (a panel or layout of both cases) it is `bare.cyl`.
- **History.** `data import history` links the OTHD and OISD files and converts each
  group (`othId`, `osgId`) once to CSV under `series/`, with FlexFlow Analyzer's handling
  of restarts and groups borrowed into FlowReel (no FlexFlow code at run time). One group
  goes to the one body; with several, each gets its own CSV, listed (commented) in
  `domain.yml` for the user to move under its body, or named at import with
  `--group N=BODY`.
- **Extract.** `data extract KIND TAG` writes under the tag's `series/` and declares
  what it wrote under the body in `domain.yml` (a name already there is replaced only
  with `--force`).
- **`--copy`** copies what would be linked, after printing its size; above 5 GB it asks
  for `--yes`. Copies get checksums in `domain.yml`.
- **Commands.** `project init` makes the folders only (`--import KIND:PATH --tag TAG`
  imports as well, and fits the first view to that tag). `data info PATH` works outside
  a project; the other `data` commands need one. `compose`, `doctor` and `jobs check`
  stay as they are.

**Branch 1: `phase9/domain-file`** (the base the others stand on)
- [x] `data/<tag>/domain.yml`: its schema and loader (kind, units, bodies with zone, file
  or function, axis, diameter, ends, series), tag names checked; the project's tags found
  under `data/`; `flowreel.yml` gains `defaults:` and `tags:`. Its `bodies:` and
  `reference:` are still read: FlowReel's own tutorials, examples and tests use them, and
  making them errors now would leave `main` failing until Phase 10 moves them; Phase 10's
  last branch removes them (decided while implementing, 2026-11-24)
- [x] Sources opened from a tag (`plt`, `vtk`, `geometry`) with the tag's bodies and units
  declared on them; the fields' parameters (`rho`, `mu`, `u_inf`) taken from the units
- [x] `data template`: every key of `domain.yml`, commented; the YAML reference covers it
- [ ] Tests on generated tags; docs (projects, bodies, sources, rules: a new rule, data by
  tag)

**Branch 2: `phase9/data-import`**
- [ ] `data import plt|vtk|geometry --path PATH --tag TAG` (`--body NAME=FILE` for VTK;
  `--name FUNCTION --param K=V` for geometry): the link, or `--copy` after the size check;
  `domain.yml` written as above; `--force`
- [ ] `data list`, `data info TAG|PATH`, `data remove TAG` (the links and `domain.yml`,
  never the case), `data rename OLD NEW` (and every file of the project that names it),
  `data check` (links that do not resolve, units not given, series files missing)
- [ ] `project init` makes the folders only, with `--import KIND:PATH --tag TAG`
- [ ] Tests on generated cases (a link, a copy, a re-import, a rename), help, docs

**Branch 3: `phase9/data-history`**
- [ ] `data import history --path PATH --tag TAG`: OTHD and OISD with FlexFlow Analyzer's
  handling of restarts and groups borrowed in; a CSV a group under `series/`; one group to
  the one body, several listed or named with `--group N=BODY`
- [ ] Tests on generated files with several groups and a restart; docs

**Branch 4: `phase9/data-extract`**
- [ ] `data extract sections TAG --body NAME`: the force on a body's sections along its
  axis, step by step from the flow (the code of PR #84), with `mu`, `rho` and `u_inf` from
  the tag's units; into `series/`, declared under the body; `--sections`, `--steps`,
  `--every`, `-j`, `--force`; steps already in the file kept
- [ ] Tests (the analytic pressure force of PR #84's tests), docs, an example

**Branch 5: `phase9/source-tags`**
- [ ] Shots name a tag (`source: TAG`, `{tag, kind, ...options}`); flow panels and layouts
  too; bodies as `tag.body` where tags meet; `source: adapter:path` still read until
  Phase 10's last branch removes it
- [ ] Frame keys, `project info`, the doctor and the camera editor follow
- [ ] Tests, docs, the YAML reference

**Branch 6: `phase9/data-migrate`** (moved to Phase 10, 2026-11-24)
- [x] Moved: the tutorials, the examples and the docs change once for both phases, in
  Phase 10's branches 6 and 7 (Section 19.11)

**Branch 7: `phase9/extract-more`** (as films need them)
- [ ] `data extract probe|table`, borrowed from FlexFlow Analyzer's `data` and `field`
  commands; each with its own task when a film asks for it

**Phase 9 is done when** branches 1 to 5 are done, with the tests and the examples on
tags. The AFMS film and both tutorials move in Phase 10, which also changes the film's
files.

### 19.11 Phase 10 tasks

Added 2026-11-24, asked by Arun after reading the tutorial ("a bit difficult to
follow"), and settled in five rounds of questions the same day (Section 24, question
12). A film is described in **levels**:

```text
film            film.yml
├── properties  output, fps, size, style
├── audio
├── watermark
└── scenes      each: a layout, a length, fades or a cross-fade, a chapter
    └── layout  inline in film.yml, or layouts/NAME.yml
        └── boxes, each one element:
            text    lines and a look; timed captions; pinned to a point of a shot box
            image   a picture: fit, opacity
            shape   a line, arrow, rectangle or circle
            shot    a shot's frames: rate, freezes
            panel   a panel's frames, drawn at the box's size
```

It replaces seven kinds of thing (film shots of kinds `card`, `frames`, `layout`,
`hold_last_of`; layout files of tiles; card files; caption files) with three nested ones:
a film of scenes, a scene a layout, a layout of boxes. A title card or credits are a
scene of text and image boxes; a plain shot is a scene of one box.

The decisions, for every branch:

- **Layouts** are written in `film.yml` under their scene, or in `layouts/NAME.yml` and
  named by it. A box has a `name`; its place is `pos: [x, y]` and `size: [w, h]` in the
  film's pixels, or `place:` (top, bottom, centre, left or right half ...); a box with
  neither fills the frame.
- **Time.** Any box shows for the whole scene unless it gives `at: [start, end]` (seconds
  into the scene) and `fade`. A scene lasts as long as its main box's frames (its shot
  or panel box, the first, or the one named `main`), freezes included; a scene of text
  and pictures gives `seconds`.
- **Text boxes** hold lines (`$...$` maths as now) and a look: `look:` (title, text,
  small) or `size`, `colour`, `align`, `weight`, `shadow`, `box`; the film's `style`
  gives the defaults. `follow: {box, model: [x, y, z], offset}` pins one to a point of
  the flow shown in a shot box, placed each frame from the camera that drew it.
- **Shape boxes** draw a line, arrow, rectangle or circle (a card's divider, a caption's
  arrow), placed like any box or following a point.
- **Image boxes** show a picture with `fit` (contain, cover, stretch), `opacity`, `at`
  and `fade`.
- **Shot and panel boxes** carry their playback: `rate: {fps, to_output}` and `freezes:
  [{at, hold}]`; other boxes go on through a freeze. Shots are rendered beforehand
  (`shot render`, or Slurm) at the size of the box that shows them unless the shot says
  otherwise; `film build` stops, naming the shot, when frames are missing. Panels in
  boxes are drawn by the build. `last_frame: SCENE` holds another scene's last frame.
- **Between scenes:** `fade: [in, out]` from and to black, and `cross: SECONDS` to
  dissolve into the next.
- **Building.** Each scene's finished clip is kept under `clips/` with a key of
  everything in it, so one changed caption rebuilds one scene. A scene's `chapter:`
  starts a chapter; every timed text box is a subtitle in `film.srt` unless it says
  `subtitle: false`.
- **Commands.** `compose` goes: `panel draw|template`; `scene preview|design|list`;
  `film build|check|lengths|srt|chapters|template` work on scenes.
- **Folders.** `shots/`, `panels/`, `layouts/`, `assets/` (pictures, fonts, sound) and
  `data/` (Phase 9); `text/` and `cards/` go.
- **The design window** (`scene design NAME`, drawn with matplotlib): draw, move and
  resize boxes, snapping to a grid and to other boxes' edges; name a box and say what
  fills it; see each box's contents (a shot's or panel's first frame, pictures, text as
  it will look); scrub through the scene's time, boxes appearing and fading. It saves
  the layout, inline or in its file.
- **The documentation** follows the levels: the tutorials; the guide in the model's
  order (the project and its data; shots and panels; the film, its scenes and layouts,
  and each kind of box; rendering, Slurm, building and checking); the reference. Both
  tutorials are rewritten from scratch around the levels.

**Branch 1: `phase10/film-model`** (the files)
- [ ] `film.yml`'s schema: properties, audio, watermark and scenes (name, layout inline
  or a file, seconds, fade, cross, chapter); the layout's schema: boxes (name, pos,
  size, place, at, fade, and one of text, image, shape, shot, panel, last_frame); loader
  and checks, errors naming the key; card and caption files and the old shot kinds go
- [ ] `film template` and a layout template, every key commented; the YAML reference
- [ ] Tests on generated films

**Branch 2: `phase10/boxes`** (drawing a frame of a scene)
- [ ] Text boxes (lines, looks, shadow and box, maths), image boxes (fit, opacity), shape
  boxes; each box's `at` and fade
- [ ] Shot and panel boxes (frames fitted to the box; panels drawn at the box's size);
  `follow` placing text and shapes on a point of a shot box; `last_frame`
- [ ] Tests against pictures drawn by hand and the old captions' golden pictures

**Branch 3: `phase10/scene-build`**
- [ ] A scene's length from its main box or `seconds`; `rate` and `freezes` on boxes;
  fades and cross-fades; a clip per scene, cached by its key
- [ ] `film build|check|lengths|srt|chapters` on scenes: subtitles from timed text boxes,
  chapters from scenes; the contact sheet
- [ ] Tests: lengths planned and measured, one changed caption rebuilding one scene

**Branch 4: `phase10/commands`**
- [ ] `panel draw|template`, `scene preview|list`; `compose` removed; `shot render`
  drawing at the size of the box that shows the shot unless the shot gives `size`
- [ ] Help, the command reference, the doctor and `project info` (scenes, layouts)

**Branch 5: `phase10/scene-design`**
- [ ] `scene design NAME`: a matplotlib window on the scene's layout: draw, move and
  resize boxes, snap to a grid and to edges; name and fill boxes; previews of their
  contents; a time slider; saving the layout inline or to its file
- [ ] Its state tested without a window (as the camera editor's), and off screen

**Branch 6: `phase10/docs`**
- [ ] The guide restructured by the levels (Section 19.11's list), each page one level;
  every page rewritten for tags and scenes; the rules page; the site's first page
- [ ] The reference generator and its tests follow

**Branch 7: `phase10/tutorials`**
- [ ] Both tutorials rewritten from scratch around the levels (a project and its data, a
  shot, a scene of one box, a layout of several, the film), on data tags; their data
  scripts write tags; their pictures made again; their follow-along tests
- [ ] Every example and its test on tags and scenes
- [ ] The layout before tags removed, once nothing uses it: `flowreel.yml`'s `bodies:` and
  `reference:`, and `source: adapter:path` in shots and panels (Phase 9 kept them read so
  `main` stayed green)

**Phase 10 is done when** the AFMS film is made from its two cases as tags and scenes
(its port, waiting for Phases 9 and 10), both tutorials are rewritten, and the guide
follows the levels.

