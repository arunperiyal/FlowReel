# Commands

`flowreel` is one program with two ways in:

- **one-shot:** `flowreel shot render carve.yml -j 16` runs one command and exits, as a
  script or a Slurm job needs;
- **interactive:** `flowreel` alone starts FlowReel's shell, with history, Tab completion
  and contexts, for the back-and-forth of building a shot.

`python -m flowreel ...` is the same, where the `flowreel` script is not on the path.

The commands are a thin layer over library functions (`flowreel.scene.render`,
`flowreel.scene.memory.measure`, `flowreel.scene.template.template`,
`flowreel.compose.panel`, `flowreel.film.scene_build.build`,
`flowreel.film.scene_build.contact`), so everything here can also be done from Python;
[rendering](making/rendering.md), [panels](shots/panels.md),
[building the film](making/build.md) and [checking it](making/check.md) explain what
those do. Runnable examples that need no
data are `examples/project/run.sh` (a [project](projects/project.md) made, used, looked at and
cleaned), `examples/shot_commands/run.sh` and `examples/film_commands/run.sh` (that one needs
ffmpeg). The
command layer is [shellkit](https://github.com/arunperiyal/shellkit).

## The shell

```text
╭─ ~/films/afms [shot:carve.yml]
╰─❯ shot preview; shot render -j 16
```

`use shot:carve.yml` sets the shot; commands that take a shot then use it when you leave
it out, and print `Using shot: ...`. `unuse shot` clears it.

`use project:~/films/afms` sets the project: a folder holding `flowreel.yml`
([projects](projects/project.md)). The `film` commands then use its `film.yml` when no film file
is given, from any folder; without a project they use `./film.yml`.

Every command except `project init`, `data info PATH`, the `template` commands and `jobs` works inside a
project. It finds the project by walking up from the file it is given (or the shell's
project, or the current folder) and stops outside one with an error saying how to make
one. Output goes under the project root wherever the command runs: frames to
`frames/`, clips to `clips/`, caches and measured timings to `.flowreel/`. `-o` still
overrides.

`use view:main` sets a view of `cameras.yml`; `camera project` then uses it when neither
`--view` nor `--track` is given. `help`, `help shot`, and
`shot render --help` show the help. Commands can be chained with `;`, and the output of
one piped to the system's commands with `|`. `-d` (or `set debug on`) shows the full
traceback when a command fails.

## `shot render`

```text
flowreel shot render [SHOT] [--frames SPEC] [--scale S | --size W H] [--force]
                     [--save-vtp DIR] [-j N] [--threads T] [--backend B] [--no-memory-check] [-o DIR]
                     [--slurm FILE] [--submit] [Slurm options] [--max-running N] [--missing]
```

With `--slurm FILE` or `--submit`, the render becomes a Slurm job array instead of
running here; see [Slurm options](#slurm-options).

Renders the shot's frames to `DIR/<shot>/frame_00000.png`. Frames whose key did not
change since they were drawn are skipped (see [rendering](making/rendering.md#frame-keys-what-is-drawn-again)).

| Option | Default | Meaning |
|---|---|---|
| `SHOT` | the `shot` context | the shot file |
| `--frames SPEC` | all | `A`, `A:B` (A to B, both included), `A:B:E` (every E-th), or a comma list: `0:10,24,40:120:20` |
| `--scale S` | none | a draft at the shot's size times S, rounded to even pixels |
| `--size W H` | none | a draft at W x H pixels |
| `--force` | off | draw the frames even when their key did not change |
| `--save-vtp DIR` | none | draw no frames; save the scene's surfaces at each step the frames show into `DIR`, for the [camera editor](shots/camera-editor.md#away-from-the-data---vtp) on another machine |
| `-j N`, `--jobs N` | 1 | frames drawn at once, each in its own process |
| `--threads T` | `min(4, cores / N)` | threads per job |
| `--backend B` | `auto` | `auto` (OSMesa, else EGL), `osmesa`, `egl` or `x` |
| `--no-memory-check` | off | draw even if the jobs look too big for the free memory ([long bodies](shots/long-bodies.md#memory)) |
| `-o DIR`, `--out DIR` | `frames/` at the project root | folder of the frame folders |

Drafts go to `DIR/<shot>@<W>x<H>/` and never mix with the full-size frames. Each frame is
reported as it finishes, then a summary:

```text
  frame_00000.png rendered 1.2 s
  frame_00008.png skipped
2 rendered, 1 skipped in 6.8 s -> frames/reveal (backend osmesa)
```


A shot file without `size` is drawn at the size of the box that shows it in the
project's film of scenes (the largest, when several do), so its frames are made at the
size they are seen; a draft (`--scale`, `--size`) scales from there.
## `shot preview`

```text
flowreel shot preview [SHOT] [--every N] [--scale S | --size W H] [-j N] [--threads T]
                      [--backend B] [-o DIR]
```

Draws frames 0, N, 2N, ... and the last, at `--scale 0.25` by default, to check the
timing of tracks before a full render. The frames go to the draft folder of that size,
so a second preview reuses them and the full-size frames are not touched.

| Option | Default | Meaning |
|---|---|---|
| `--every N` | 10 | draw every N-th frame (and the last) |
| `--scale S` | 0.25 | size of the preview; or `--size W H` |

The other options are those of `shot render`.

## `shot memory`

```text
flowreel shot memory [SHOT] [--frame N] [--scale S | --size W H] [--threads T] [--backend B]
```

Draws one frame in a fresh process, as `render` does, and reports its peak memory, the
free memory and cores (this machine's, or in a Slurm job the job's; the brackets say
which, see [rendering](making/rendering.md#inside-a-slurm-job)), and the number of jobs that
fit (80% of the free memory, at most one per core, or cores / T with `--threads T`):

```text
frame 0: peak 0.98 GB in 1.1 s
source estimate for one step: 0.01 GB
free memory 22.5 GB, 16 cores (this machine, MemAvailable); measured with 4 threads
suggested jobs: -j 16
```

`--frame` defaults to 0: in a frozen shot it is the frame that contours. Measure on the
machine that will render, with the size it will render at.

## `shot template`

```text
flowreel shot template [NAME] [--layers TYPES] [-o FILE] [--force]
```

Prints a shot file with every key and every option of the chosen layer types at its
default, each with a comment saying whether it is a track, its unit or choices. It is
generated from the code's own option lists, so it is always current. Options with no
default are written commented out; required ones get an example value, so the file loads
once `source` and `camera` name real things.

| Option | Default | Meaning |
|---|---|---|
| `NAME` | `my_shot` | the shot's `name` |
| `--layers TYPES` | `body` | comma list of layer types: `body`, `slice`, `iso`, `outline`, `glyphs`, `markers3d`, `geometry`, `supports`, `centreline`, `axes` |
| `-o FILE` | print | write to FILE |
| `--force` | off | overwrite FILE if it exists |

## Camera commands

Every camera command reads and writes one `cameras.yml`: `-c FILE`, else the project's,
at its root ([projects](projects/project.md)). Files
are written by [`update_cameras`](shots/cameras.md#writing-camerasyml): other views and tracks
are kept, the old file is left as `cameras.yml.bak`, and comments are not kept.

### `camera edit`

```text
flowreel camera edit [SHOT] --track NAME [--frames N] [--vtp DIR] [--film FILE]
                     [--spline] [--size W H] [-c FILE]
```

Opens the [camera editor](shots/camera-editor.md) on the shot's scene: move the camera, set the
Frame slider, press `s` to save a key. Keys: `s` save, `u` undo, `r` replace nearest,
`p` play, `n` next step. Every change is written at once.

| Option | Default | Meaning |
|---|---|---|
| `SHOT` | the `shot` context | the shot whose scene is shown |
| `--track NAME` | required | the track to make, or to take up where it was left |
| `--frames N` | the shot's frames | the track's length; needed with `--vtp` and no shot |
| `--vtp DIR` | none | open surfaces saved by `shot render --save-vtp DIR` instead of the data |
| `--film FILE` | none | mark the points of the flow that this film's boxes follow on the shot |
| `--spline` | off | write the track with `path: spline` |
| `--size W H` | `1280 720` | the window's size |

Where there is no display (`DISPLAY` or `WAYLAND_DISPLAY` unset on Linux) it stops at
once with an error saying to save the surfaces and open them elsewhere.

### `camera path`

```text
flowreel camera path NAME --keys F:VIEW[:EASE] ... [--path linear|spline] [--ease E]
                     [--frames N] [-c FILE]
```

Writes a track from keys, frames increasing; a key's `EASE` sets the segment from it to
the next ([camera tracks](shots/cameras.md#camera-tracks)).

| Option | Default | Meaning |
|---|---|---|
| `--keys` | required | `FRAME:VIEW` or `FRAME:VIEW:EASE`, views of `cameras.yml` |
| `--path` | `linear` | through the keys: `linear` or `spline` |
| `--ease E` | `smooth` | the segments' easing unless a key gives one |
| `--frames N` | none | the track's length |

### `camera orbit`

```text
flowreel camera orbit NAME --radius R --frames N (--target X Y Z | --shot FILE --station S
                      [--body B] [--step N]) [--azimuth A] [--span S] [--elevation E [E2]]
                      [--axis x|y|z] [--up X Y Z] [--lead L] [--view-angle DEG] [--ease E] [-c FILE]
```

Writes views `NAME_00`, `NAME_01`, ... and a track that circle a target
([orbits](shots/cameras.md#orbits)). The target is a point, or a body's centre at a station
along its axis, found in the shot's source as `follow` finds it.

| Option | Default | Meaning |
|---|---|---|
| `--radius R` | required | the camera's distance from the target |
| `--frames N` | required | the track's length |
| `--target X Y Z` | | a point; or give `--station` |
| `--station S` | | where along the body's axis; with `--shot` |
| `--shot FILE` | | the shot whose source has the body |
| `--body B` | the one body | a body of that source |
| `--step N` | the first | the body at this step |
| `--azimuth A` | `0` | where the orbit starts, degrees |
| `--span S` | `360` | degrees turned; positive is anticlockwise seen from the axis tip |
| `--elevation E [E2]` | `0` | degrees above the plane across the axis, or from and to |
| `--axis` | `y`; with `--station`, the body's axis | what the camera turns about; the station is always along the body's own axis |
| `--up X Y Z` | the axis | the camera's up |
| `--lead L` | `0` | the focal point moved this far along the turn axis |
| `--view-angle` | `30` | degrees |
| `--ease E` | `smooth` | over the whole turn |

### `camera import`

```text
flowreel camera import FILE [NAME] [--index I] [--view V] [--force] [-c FILE]
```

Adds the camera of a ParaView state (`.pvsm`), a ParaView Python state or trace (`.py`),
or a YAML camera frame or another `cameras.yml` (`.yml`) as view `NAME` (default
`main`). `--index I` picks a render view of a ParaView file (from 0), `--view V` a view of
a `cameras.yml`. A view of the same name is replaced only with `--force`
([importing a view](shots/cameras.md#importing-a-view)).

### `camera project`

```text
flowreel camera project (--view V | --track T) --points X,Y,Z ... [--size W H]
                        [--frames SPEC] [-c FILE]
```

Prints where model points land on the screen, in pixels from the upper left with `y`
down, for a view, or for each frame of a track (`--frames`: `A:B:E` or a list; default
every frame). A point behind the camera prints `behind`. `--size` is the picture's
(default `1920 1080`). In the shell, `use view:main` and `--view` can be left out
(an explicit `--track` wins over it).

```text
$ flowreel camera project --track turn --points 6,0,0 6,0.5,0 --frames 0:47:23
frame                   6,0,0                 6,0.5,0
    0          (959.9, 540.0)          (959.9, 374.2)
   23          (960.0, 540.0)          (960.0, 379.5)
   46          (960.1, 540.0)          (960.1, 388.1)
```

### `camera preview`

```text
flowreel camera preview TRACK [SHOT] [--vtp DIR] [--every N] [--scale S] [-o DIR] [-c FILE]
```

Draws every `N`th frame of a track (and its last) small, over one scene: the shot's first
step, or saved surfaces (`--vtp`). Nothing else changes between the frames, so it shows
the camera move in a second or two, without rendering the shot. Frames go to
`DIR/<track>@preview/` (default `frames/` at the project root); `--scale` is of the shot's size (default
`0.25`; 1920x1080 with `--vtp` and no shot).

See `examples/camera_commands/run.sh`, which runs each of these on generated data.

## `panel draw`

```text
flowreel panel draw PANEL [--frames SPEC] [--force] [-j N] [-o DIR] [Slurm options]
```

Draws a panel's own frames into `frames/<panel>/`, frame *i* at the panel's time *i*,
skipping frames whose key did not change ([panels](shots/panels.md)). In a film of scenes
a panel box needs no draw: the build draws the panel at the box's size.

## `panel template`

```text
flowreel panel template [--type series|phase|map|locator|section|cuts|strip] [-o FILE] [--force]
```

A working panel file of a type, for a project of tags (bodies as `tag.body`, sources by
tag), with the type's other keys commented.

## `scene list`

```text
flowreel scene list [FILM]
```

Each scene of a film of scenes: where it starts, how long it lasts, its boxes (the main
one marked), its layout file, chapter and cross ([a film of scenes](film/film.md)). A
scene whose shot has no frames yet is listed with its length unknown, and says why.

## `scene preview`

```text
flowreel scene preview NAME [--at S ...] [--every S] [-o DIR] [--film FILM]
```

Stills of one scene, as the build draws its frames (before the scene's fades), into
`frames/scenes/NAME/at_S.png`: by default at its start, middle and end. Nothing is
encoded, so a layout's places and text are seen in seconds. Shot boxes need their
frames; a held last frame shows once its scene's clip is built.

## `scene design`

```text
flowreel scene design NAME [--grid PX] [--film FILM]
```

A window to draw, move, resize, name and fill a scene's boxes, with the scene drawn at
a time you choose; every change is checked and written at once
([designing a layout](film/layouts.md#designing-a-layout-scene-design)).

## `film build`

```text
flowreel film build [FILM] [--only SCENE] [--mute] [--force] [--preview HEIGHT]
                    [--crf N] [--watch] [--clips DIR] [Slurm options]
```

Builds the [film](film/film.md): every scene's finished clip, kept when its key did not
change, joined into the film's `output` with its sound and chapters; then `film.srt` and
`chapters.txt` beside it ([building the film](making/build.md)). Prints each scene's
planned and measured length and whether its clip was built or kept. `film check`,
`lengths`, `srt` and `chapters` read the same file.

| Option | Default | Meaning |
|---|---|---|
| `FILM` | the project's `film.yml`, else `./film.yml` | the film file |
| `--only SCENE` | none | build that scene's finished clip alone, copied to `film_SCENE.mp4`, silent, for checking its text |
| `--mute` | off | build the film without its sound |
| `--force` | off | build every clip again, even when its key did not change |
| `--preview HEIGHT` | none | also write `film_<HEIGHT>p.mp4`, scaled to HEIGHT pixels (even, at most the film's) |
| `--crf N` | `28` | quality of the preview copy, 0 to 51, lower is better and larger; needs `--preview` |
| `--watch` | off | build, then build again on each change to a file the film may be made from, until Ctrl-C ([building as you edit](making/build.md#building-as-you-edit---watch)) |
| `--clips DIR` | `clips/` at the project root | folder of the clips |

```text
$ flowreel film build --preview 180
shot     planned  measured
opening    2.00 s    2.00 s  built
wake       4.50 s    4.50 s  built
end        2.00 s    2.00 s  built
film       8.50 s    8.50 s  film.mp4
preview film_180p.mp4
srt film.srt
chapters chapters.txt
audio tone.wav: 0.00 to 8.50 s of the film (file 20.00 s)
built in 6.1 s
```

## `film check`

```text
flowreel film check [FILM] [--at WHEN] [--columns N] [--width PX] [-o FILE] [--force]
                    [--clips DIR] [-j N]
```

Draws a [contact sheet](making/check.md#contact-sheet-contactpng): stills of the finished
film, each labelled with its time and scene. Missing scene clips are built; the film is
not joined, so the sheet comes before the build.

| Option | Default | Meaning |
|---|---|---|
| `--at WHEN` | `caption` | `caption` (the middle of each timed text box), `freeze` (the middle of each freeze) or `every:S` (every S seconds) |
| `--columns N` | `4` | stills across the sheet |
| `--width PX` | `480` | width of a still, at most the film's |
| `-o FILE`, `--output FILE` | `contact.png` beside the film | the sheet |

`--force` and `--clips` are those of `film build`.

## `film lengths`

```text
flowreel film lengths [FILM] [--clips DIR]
```

Prints each scene's planned length and its measured length, from its clip when it is
built and current (`-` when it is not), then each chapter's start and length
([checking the film](making/check.md)). Nothing is drawn or built, so it answers at once.

```text
$ flowreel film lengths
scene    planned  measured
opening    2.00 s    2.00 s
wake       4.50 s    4.50 s
end        2.00 s    2.00 s
film       8.50 s    8.50 s
chapter   start             length
Opening      0:00     0.00 s    2.00 s
The wake     0:02     2.00 s    5.00 s
Thanks       0:07     7.00 s    1.50 s
```

## `film srt`

```text
flowreel film srt [FILM] [-o FILE]
```

Writes the timed text boxes as [SubRip subtitles](making/build.md#subtitles-filmsrt) at
their film times (default `film.srt` beside the film), maths as plain text. Nothing is
built.

## `film chapters`

```text
flowreel film chapters [FILM] [-o FILE]
```

Prints the [chapters](making/build.md#chapters) as `chapters.txt` holds them, `0:00 Title` per
line, ready for a YouTube description, or writes them to FILE. What YouTube would
refuse (no chapter at 0:00, fewer than three, one shorter than 10 s) is noted on
stderr, so the printed list can be piped. Nothing is built.

## `film template`

```text
flowreel film template [NAME] [--fps N] [-o FILE] [--force]
flowreel film template --layout [-o FILE] [--force]
```

`film template` prints a film of scenes with every key at its default, each with a comment: a
title scene, a scene of the shot `shots/NAME.yml` (default `my_shot`), and an end scene
holding its last frame ([the film](film/film.md)). `--layout` prints a layout file with
one box of each kind ([layouts and boxes](film/layouts.md)). The defaults are taken from
the code, so the files are always current.

## `project init`

```text
flowreel project init [--import plt|vtk:PATH --tag TAG] [-o DIR] [--force]
```

Makes the project folder `DIR` ([projects](projects/project.md)) and, with `--import`,
brings the first case in as a tag, as [`data import`](#data-import) does: its bodies and
units are in `data/TAG/domain.yml`, and `cameras.yml`'s first view is fitted to it.

It makes `shots/`, `panels/`, `layouts/`, `assets/` and `data/`; `film.yml` (from
`film template`) and `cameras.yml` (one view `main`, a placeholder until `--import` fits
it to the case) at the root, kept if they exist; a `.gitignore` for `frames/`, `clips/`,
`.flowreel/` and `data/`; and `flowreel.yml`, which marks the folder as a project and has
only comments. A case's bodies, units and series are written in its tag's `domain.yml`
([bodies](projects/bodies.md)).

| Option | Default | Meaning |
|---|---|---|
| `--import KIND:PATH` | none | the first case, as `data import KIND --path PATH` brings it in; with `--tag` |
| `--tag TAG` | none | its tag |
| `-o DIR`, `--out DIR` | `.` | project folder |
| `--force` | off | overwrite an existing `flowreel.yml`; `film.yml` and `cameras.yml` are kept |

```text
$ flowreel project init -o carve --import plt:/scratch/carve/binary --tag carve
linked carve/data/carve/plt -> /scratch/carve/binary
wrote carve/data/carve/domain.yml: fill in the units
made carve: shots/ panels/ layouts/ assets/ data/
wrote carve/film.yml, carve/cameras.yml, carve/.gitignore
wrote carve/flowreel.yml; the case's bodies and units are in data/carve/domain.yml
```

## `project info`

```text
flowreel project info [DIR]
```

Prints what the project holds: its tags, the sources its shots read, the bodies (of
the tags, as `tag.body`), every shot file with the frames drawn for it, the views and tracks of
`cameras.yml`, the film's scenes and layout files, and the size of `frames/`, `clips/`
and `.flowreel/`. A file that does not load is listed with its error. Nothing is
changed. `DIR` is any folder in the project (default: the shell's project, else the
current folder).

## `data template`

```text
flowreel data template [--kind plt|vtk|geometry] [-o FILE] [--force]
```

Prints a tag's `domain.yml` with every key, at its default or as an example, each with
a comment ([data and tags](projects/data.md)); `-o` writes it.

## `data import`

```text
flowreel data import plt|vtk|geometry --tag TAG [--path PATH] [--copy [--yes]] [--force]
                     [--body NAME=FILE ...] [--flow FILE]        (vtk)
                     [--name FUNCTION] [--param KEY=VALUE ...]   (geometry)
flowreel data import history --path CASE --tag TAG [--group N=BODY ...] [--copy] [--force]
```

Links the case under `data/TAG/` (or copies it with `--copy`) and writes its measured
`domain.yml`; `--force` re-imports into a tag, keeping the file's edits
([bringing a case in](projects/data.md#bringing-a-case-in)). `history` converts a FlexFlow case's
OTHD and OISD groups to CSV in a tag that holds its flow, and declares them under its
bodies ([histories from FlexFlow](projects/data.md#histories-from-flexflow)).

## `data extract`

```text
flowreel data extract sections TAG [--body NAME] [--axis x|y|z] [--sections N]
                      [--steps FIRST LAST] [--every N] [--margin L] [-j N] [--force]
```

Computes a series from a tag's flow into `data/TAG/series/` and declares it under the
body. `sections` gives the force on equal sections along the body's axis, step by step,
with the constants from the tag's units. Steps already in the file are kept
([series from the flow](projects/data.md#series-from-the-flow-data-extract)).

## `data list`, `info`, `check`, `rename`, `remove`

```text
flowreel data list
flowreel data info TAG|PATH
flowreel data check [TAG ...]
flowreel data rename OLD NEW
flowreel data remove TAG [--yes]
```

See [looking after the tags](projects/data.md#looking-after-the-tags). `data info PATH`
works outside a project; `data check` exits with status 1 when a tag has a problem.

## `project clean`

```text
flowreel project clean [DIR] [--cache] [--frames] [--clips] [--dry-run]
```

Removes generated output: `--cache` (`.flowreel/cache/`, the default when none is
named), `--frames` (`frames/`) and `--clips` (`clips/`), and prints the size of each.
Files written by hand, the data, and the measured frame costs and job records in
`.flowreel/` are never removed; they are small and size the next Slurm job. A folder
that is a symbolic link is skipped, since what it points to may be shared.

| Option | Default | Meaning |
|---|---|---|
| `--cache` | on when none is named | the surface cache |
| `--frames` | off | every frame folder |
| `--clips` | off | the finished clips |
| `--dry-run` | off | say what would be removed, remove nothing |

## Slurm options

`shot render`, `panel draw` and `film build` run as Slurm jobs when
given `--slurm FILE` (write the job script to FILE) or `--submit` (write it, to
`jobs/NAME.sh` unless `--slurm` names one, and hand it to `sbatch`). The job runs the
same command in this folder, from this environment. See [Slurm](making/slurm.md) for how a
render is sized and split.

| Option | Default | Meaning |
|---|---|---|
| `--slurm FILE` | | write the job script to FILE |
| `--submit` | off | submit it with `sbatch`; prints the job id and the log |
| `--cluster NAME` | `FLOWREEL_CLUSTER`, else this host's | the cluster of [the partition table](making/slurm.md#clusters-and-partitions) |
| `--partition NAME` | the shortest that takes the job | the partition |
| `--time T` | estimated for a render, 2 h otherwise | `90m`, `3h`, `1-12:00:00` |
| `--mem SIZE` | worked out for a render, 16 GB otherwise | `32G`, `500M` |
| `--cpus N` | 16 for a render, 4 otherwise | cores of a job (a render's task) |
| `--after JOBID` | | start only when that job ended well; may be repeated |
| `--max-running N` | as Slurm schedules | `shot render`: at most N tasks at once, so the render takes part of a node |
| `--missing` | off | `shot render`: tasks only for frames not drawn yet |

A render is sized from the measured cost of one frame, kept beside its frames by every
render and by `shot memory`. A shot not measured yet gets a measuring job first, which
then submits the render from the node:

```text
$ flowreel shot render reveal.yml --submit --max-running 2
reveal: no measurement of a frame yet; the job measures one on the node, then plans and submits the render as reveal.sh
wrote jobs/reveal_measure.sh (measuring job)
submitted job 1310; log logs/reveal_measure_1310.log

$ flowreel shot render reveal.yml --submit --max-running 2       # once measured
121 frames in 1 task of up to 121 frames, 1 at once
each task: 16 cores, 15G, -j 16 --threads 1, 00:11:12 on airavata part1 (drawing about 00:00:48)
one frame: 0.70 GB and 6.0 s a frame (1 frame, 1 thread, node1, 2026-11-21 04:00)
wrote jobs/reveal.sh (job array of 1 task)
submitted job 1311; log logs/reveal_1311_*.log
```

A film as a chain: render the shots, then build the film after them (the build draws
the panel boxes itself).

```bash
flowreel shot render bare_wake.yml --submit           # job 1320
flowreel shot render helical_wake.yml --submit        # job 1321
flowreel film build --submit --after 1320 --after 1321 --preview 480
```

## `jobs partitions`, `jobs check`, `jobs status`

```text
flowreel jobs partitions [--cluster NAME]
flowreel jobs check [--backend B] [--timeout S]
flowreel jobs status [JOBID ...] [--all]
```

- **`partitions`** lists the clusters and partitions FlowReel knows, its own table and
  `~/.flowreel/partitions.yml`, marking this machine's cluster.
- **`check`** draws a tiny picture with each off-screen backend, each in its own process,
  and says which work; it exits 1 when the one renders would use does not. Every job
  script runs it first, so a node without OpenGL fails in seconds.
- **`status`** gives Slurm's state of the jobs submitted from this folder (the last ten,
  or `--all`; noted in `.flowreel/jobs.json` at the project root) or of the jobs given: `squeue` for those
  queued or running, `sacct` for the rest. For a render it counts the frames drawn since
  it was submitted.

```text
$ flowreel jobs status
1311  reveal (render), submitted 00:04:10 ago
  RUNNING for 00:04:02
  frames drawn since: 64 of 121 (frames/reveal)
1312  film (film), submitted 00:04:09 ago
  PENDING (Dependency)
```

One job is described in words: why it waits (Slurm's reason, such as `Dependency` on
the jobs it runs `--after`), how long it has run, or how it ended. An array of tasks is
counted by state, such as `RUNNING 4, PENDING 12`.

## `doctor`

```text
flowreel doctor [--no-draw] [--timeout S]
```

One report of what FlowReel runs on, to read when something looks wrong, or to send
with a question:

```text
$ flowreel doctor
FlowReel:
   flowreel    0.0.1 at /home/you/FlowReel/src/flowreel
   python      3.12.12 at /home/you/miniconda3/envs/flexflow_env/bin/python
packages:
   numpy       2.4.2 (needs 1.26 or newer)
   pyvista     0.49.2, tested (0.47 to 0.49)
 ? vtk         9.8.0, newer than tested (9.5 to 9.7): untested, may draw differently
   matplotlib  3.10.9, tested (3.8 to 3.10)
   ...
ffmpeg:
   ffmpeg      8.0.1 at /home/you/miniconda3/envs/flexflow_env/bin/ffmpeg, with the encoder and filters FlowReel uses
off-screen drawing:
   osmesa      not installed
   egl         works in 1.2 s
   used        egl: works
fonts:
   Lato        the copy bundled with FlowReel, at /home/you/FlowReel/src/flowreel/fonts
project:
   folder      /home/you/films/cylinder
   shots       2
   film        film.yml: 5 shots, 20.0 s planned
everything FlowReel needs is here
```

Each package is checked against the minimum FlowReel declares. VTK, pyvista and
matplotlib, which decide what a frame or a caption looks like, are also checked against
the oldest and newest versions the tests run on in CI: a newer one works as far as anyone knows, but has not been
tested (`?`). A package older than the minimum, no ffmpeg FlowReel can use, or no back
end that draws (`!`) stops a film, and the exit status is 1. The drawing is the test of
[`jobs check`](#jobs-partitions-jobs-check-jobs-status); `--no-draw` leaves it out.

## Errors and exit status

A problem in a shot, layout, panel or film file is reported with the file and key path, and the nearest valid
key when there is a typo; no traceback:

```text
Error: carve.yml: sise: unknown key 'sise' (allowed: ...); did you mean 'size'?
```

The exit status is 0 on success, 2 for a wrong option or shot file, 1 for any other
failure, and 130 when stopped with Ctrl-C.
