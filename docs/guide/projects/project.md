# Projects: one folder per film

A FlowReel project is a folder with a `flowreel.yml` in it. Every file of one film lives
there: the data, brought in as [tags](data.md); the shots and panels; the film file with
its scenes and their layouts; the cameras; the pictures and sound. The commands work
inside it, from any of its folders, and put what they make in the same places every
time. The rules are decided in the plan (Section 23, question 6; Section 24, questions 11
and 12); this page says what they mean in use. All of FlowReel's rules are listed in
[rules](rules.md).

## Making one

```text
$ flowreel project init -o afms --import plt:/scratch/afms/bare/binary --tag bare
linked afms/data/bare/plt -> /scratch/afms/bare/binary
wrote afms/data/bare/domain.yml: fill in the units
made afms: shots/ text/ cards/ assets/ data/
wrote afms/film.yml, afms/cameras.yml, afms/.gitignore
wrote afms/flowreel.yml; the case's bodies and units are in data/bare/domain.yml
```

`--import KIND:PATH --tag TAG` brings the first case in as a tag, as
[`data import`](data.md#bringing-a-case-in) does, and fits the first view of
`cameras.yml` to it. More cases come in with `data import` later. `flowreel project init`
alone makes the folders and a `flowreel.yml` with only comments, which is enough to make
a folder a project (for example on a laptop with only saved surfaces and `cameras.yml`,
to run `camera edit`). Options: [commands](../commands.md#project-init).

## What is in it

```text
afms/
├── flowreel.yml      the project's defaults and tags; marks its root
├── film.yml          the film: its scenes, sound and watermark
├── cameras.yml       every view and camera track of the project
├── data/<tag>/       each case: a link to its data, domain.yml, series/
├── shots/            shot files
├── panels/           panel files
├── layouts/          layouts shared by scenes
├── assets/           pictures, fonts and sound you have the right to use
├── frames/           generated: one folder of frames per shot, panel or draft
├── clips/            generated: each scene's clip
└── .flowreel/        generated: caches, measured frame costs, Slurm job records
```

| Path | Written by | Kept in git | Notes |
|---|---|---|---|
| `flowreel.yml` | you (`project init` starts it) | yes | marks the project root; [defaults and tags](#defaults-and-tags) |
| `film.yml` | you (`film template` starts one) | yes | [the film](../film/film.md) |
| `cameras.yml` | you and the camera commands | yes | one for the whole project; [cameras](../shots/cameras.md) |
| `shots/`, `panels/`, `layouts/`, `assets/` | you | yes | the names are a convention; files anywhere in the project work |
| `data/` | `data import`, `project init --import` | each tag's `domain.yml` only | the [tags](data.md): links to the data, `domain.yml`, series |
| `frames/`, `clips/` | `shot render`, `panel draw`, `film build` | no | removed by `project clean --frames`, `--clips` |
| `.flowreel/` | every command | no | `cache/` removed by `project clean`; see below |

`project init` never overwrites `film.yml` or `cameras.yml` (not even with `--force`), and
adds to an existing `.gitignore` only the lines it lacks.

**Why `flowreel.yml` is visible and `.flowreel/` hidden.** What a person edits stays in
plain view; what only FlowReel reads is out of the way, so `ls` shows the film and not
its machinery. Nothing in `.flowreel/` needs editing, and deleting it costs only time.

**Why the data is linked.** A case is often hundreds of gigabytes on scratch storage,
and belongs to the simulation rather than the film. The link records where it is
without copying it, and the `.gitignore` leaves each tag's link and series out of git, so
the repository never holds the data; the `domain.yml` you edit is kept. (A project made
before tags has `data/` in its `.gitignore`; change it to `data/*/*` and
`!data/*/domain.yml` to keep its tags' files.)

## Defaults and tags

```yaml
defaults:
  backend: auto
  style: {font: Times New Roman, maths: stix}
tags: [bare, helical]
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `defaults` | mapping | `{}` | what the project's commands start from |
| `defaults.backend` | `auto`, `osmesa`, `egl`, `x` | `auto` | the off-screen back end |
| `defaults.style` | mapping | the film's own | the film's style |
| `tags` | list of tag names | the folders of `data/` | the project's [tags](data.md), listed for checks |

Each case's bodies, units and series are in its tag's `domain.yml`
([data and tags](data.md)), not here: two cases may then name a body alike.

## Reference values

Going. Before tags, the flow's reference values were given once in `flowreel.yml`, with its
`bodies:` ([bodies](bodies.md)). Both are still read, for projects that have not moved
to tags, and go once FlowReel's own tutorials and examples no longer use them. A tag's
[units](data.md#units) take their place.

```yaml
reference: {rho: 1000.0, u_inf: 0.5, length: 0.05}
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `reference.rho` | number > 0 | none | density, in the source's units |
| `reference.u_inf` | number > 0 | none | free-stream speed, in the source's units |
| `reference.length` | number > 0 | none | the unit of the axes layer's `unit: diameters` when it names no `body` |

A shot of a tag takes its tag's units instead; the values are part of each frame's key
either way, so changing them draws the frames that use them again.

## Finding the project

A command finds its project by walking up from the file it was given (a shot, panel,
layout or film file), else from the shell's `use project:DIR`, else from the current
folder, to the nearest folder with `flowreel.yml`. So `flowreel shot render cylinder.yml`
works the same in `afms/shots/` as `flowreel shot render shots/cylinder.yml` in `afms/`.

Outside a project the commands stop:

```text
$ flowreel shot render wake.yml
Error: /home/a/wake.yml is not in a FlowReel project (no flowreel.yml there or in any
folder above). Make one with 'flowreel project init' in the project's folder (for
example: flowreel project init vtk:run/flow.pvd), or cd into one. Reference: docs/guide/projects/project.md
```

`project init`, `data info PATH`, the `template` commands and the `jobs` commands
work anywhere.
The Python library has no such rule: `flowreel.scene.render("wake.yml")` works in any
folder, and outside a project keeps its files beside the shot as before.

## Where output goes

Wherever a command runs, its output goes under the project root:

| What | Where | Overridden by |
|---|---|---|
| frames of a shot or a panel | `frames/<name>/`, a draft in `frames/<name>@<W>x<H>/` | `-o DIR` |
| stills of a scene | `frames/scenes/<scene>/` | `-o DIR` |
| camera previews | `frames/<track>@preview/` | `-o DIR` |
| scenes' clips, shots' interpolated base clips | `clips/` | `--clips DIR` |
| the film, `film.srt`, `chapters.txt`, `contact.png` | beside `film.yml` (the root) | `output:` in `film.yml`, `-o FILE` |
| surface cache of frozen shots | `.flowreel/cache/surfaces/` | |
| measured cost of a frame | `.flowreel/measured/<frame folder>.json`, e.g. `.flowreel/measured/frames/wake.json` | |
| Slurm job scripts | `jobs/` | `--slurm FILE` |
| record of submitted jobs | `.flowreel/jobs.json` | |

Frame keys (`.keys.json`) and each frame's camera (`.views.json`) stay inside the frame
folder: they describe those frames, and a frame folder copied elsewhere keeps them.

Jobs run at the project root, so the paths in a job script's command lines are written
relative to it, and `jobs status` reads the record of the project you are in.

## One `cameras.yml`

Every shot of the project reads the `cameras.yml` at the root, so shots in `shots/` share
the same views and tracks. The camera commands write there too, unless given `-c FILE`. A `cameras.yml` left
beside a shot below the root is an error, rather than being read or quietly ignored:

```text
Error: afms/shots/cameras.yml: a project has one cameras.yml, at its root; move this one
to afms/cameras.yml (merge their views and tracks if both exist)
```

Paths written inside files (a shot box's shot file, a layout's picture, a tag's `source`)
are still relative to the file that holds them.

## Looking at a project, and cleaning it

```text
$ flowreel project info
project /home/a/films/afms
source:  bare, helical
tags:    bare (plt, 121 steps); helical (plt, 121 steps)
bodies:  bare.cyl, helical.cyl
shots:   2
  shots/reveal.yml: reveal, 288 frames drawn
  shots/wake.yml: wake, 0 frames drawn (25 in drafts)
cameras: views main, side; tracks approach
film:    film.yml: 5 scenes
scenes:  opening, reveal, compare, lift, end
layouts: compare
output:  frames/ 1.9 GB, clips/ 84.2 MB, .flowreel/ 12.0 MB
```

A file that does not load is listed with its error rather than stopping the report.

```text
$ flowreel project clean --frames --dry-run
would remove frames/ (1.9 GB)
would remove 1.9 GB in all
$ flowreel project clean
removed .flowreel/cache/ (11.9 MB)
removed 11.9 MB in all
```

`project clean` removes the caches by default; `--frames` and `--clips` remove the frames
and clips, which cost hours to make again, so they are only removed when named. It never
removes files written by hand, the data, or the measured costs and job records (small,
and they size the next Slurm job). A generated folder that is a symbolic link (frames on
scratch storage, say) is skipped: what it points to may be shared.

## Example

`examples/project/run.sh` makes a project with a linked stand-in for the data, renders a
shot from inside `shots/` (the frames land in the root's `frames/`), then runs
`project info` and `project clean`. It needs no data and no display, only off-screen
rendering.

```text
sh examples/project/run.sh /tmp/project_example
```

## From Python

| Function | Does |
|---|---|
| `flowreel.project.init.make_project(folder, ...)` | lays out the folder, returns what it wrote and kept |
| `flowreel.project.imports.import_data(root, kind, path, tag)` | brings a case in as a tag |
| `flowreel.project.paths.find_root(start)` | the project root holding `start`, or `None` |
| `flowreel.project.paths.require_root(start)` | the same, or `NotInProject` saying how to make one |
| `flowreel.project.paths.cameras_file(start)` | the `cameras.yml` a file there uses |
| `flowreel.project.paths.output(start, "frames")` | `<root>/frames`, or beside `start` outside a project |
| `flowreel.project.info.info(root)`, `.clean(root, ["cache"], dry_run=False)` | `project info` and `project clean` |
