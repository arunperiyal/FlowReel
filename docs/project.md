# Projects: one folder per film

A FlowReel project is a folder with a `flowreel.yml` in it. Every
file of one film lives there: the shots, the captions, the cards, the cameras, the film
file, and a link to the data. The commands work inside it, from any of its folders, and
put what they make in the same places every time. The rules are decided in the plan
(Section 23, question 6); this page says what they mean in use. All of FlowReel's rules,
these and the others, are listed in [rules](rules.md).

## Making one

```text
$ flowreel project init vtk:data/run/flow.pvd --link /scratch/afms/run -o afms
linked afms/data/run -> /scratch/afms/run
made afms: shots/ text/ cards/ assets/ data/
wrote afms/film.yml, afms/cameras.yml, afms/.gitignore
wrote afms/flowreel.yml: 1 body (cylinder); fill in the supports
```

`--link` is done first, so `SOURCE` can read the data through the link. `SOURCE` may be
left out: `flowreel project init` alone makes the folders and a `flowreel.yml` with only
comments, which is enough to make a folder a project (for example on a laptop with only
saved surfaces and `cameras.yml`, to run `camera edit`). Options: [commands](commands.md#project-init).

## What is in it

```text
afms/
├── flowreel.yml      bodies (and later the project's defaults); edited by hand
├── film.yml          the film: shots in order, captions, sound
├── cameras.yml       every view and camera track of the project
├── shots/            shot files
├── text/             caption files
├── cards/            title and end cards
├── assets/           images, fonts and sound you have the right to use
├── data/             links to the simulation's output (never copies)
├── frames/           generated: one folder of frames per shot or draft
├── clips/            generated: each shot's encoded clips
└── .flowreel/        generated: caches, measured frame costs, Slurm job records
```

| Path | Written by | Kept in git | Notes |
|---|---|---|---|
| `flowreel.yml` | you (`project init` starts it) | yes | marks the project root; [bodies](bodies.md) |
| `film.yml` | you (`project init` writes `film template`'s) | yes | [film](film.md) |
| `cameras.yml` | you and the camera commands | yes | one for the whole project; [cameras](cameras.md) |
| `shots/`, `text/`, `cards/`, `assets/` | you | yes | the names are a convention; files anywhere in the project work |
| `data/` | `project init --link` | no | symbolic links to the data |
| `frames/`, `clips/` | `shot render`, `compose`, `film build` | no | removed by `project clean --frames`, `--clips` |
| `.flowreel/` | every command | no | `cache/` removed by `project clean`; see below |

`project init` never overwrites `film.yml` or `cameras.yml` (not even with `--force`, which
only rewrites `flowreel.yml` and replaces a data link), and adds to an existing
`.gitignore` only the lines it lacks.

**Why `flowreel.yml` is visible and `.flowreel/` hidden.** What a person edits stays in
plain view; what only FlowReel reads is out of the way, so `ls` shows the film and not
its machinery. Nothing in `.flowreel/` needs editing, and deleting it costs only time.

**Why the data is linked.** A case is often hundreds of gigabytes on scratch storage,
and belongs to the simulation rather than the film. The link records where it is
without copying it, and `data/` is left out of git so the repository never holds it.

## Finding the project

A command finds its project by walking up from the file it was given (a shot, layout,
panel or film file), else from the shell's `use project:DIR`, else from the current
folder, to the nearest folder with `flowreel.yml`. So `flowreel shot render cylinder.yml`
works the same in `afms/shots/` as `flowreel shot render shots/cylinder.yml` in `afms/`.

Outside a project the commands stop:

```text
$ flowreel shot render wake.yml
Error: /home/a/wake.yml is not in a FlowReel project (no flowreel.yml there or in any
folder above). Make one with 'flowreel project init' in the project's folder (for
example: flowreel project init vtk:run/flow.pvd), or cd into one. Reference: docs/project.md
```

`project init`, `shot template`, `film template` and the `jobs` commands work anywhere.
The Python library has no such rule: `flowreel.scene.render("wake.yml")` works in any
folder, and outside a project keeps its files beside the shot as before.

## Where output goes

Wherever a command runs, its output goes under the project root:

| What | Where | Overridden by |
|---|---|---|
| frames of a shot, a layout, a panel | `frames/<name>/`, a draft in `frames/<name>@<W>x<H>/` | `-o DIR` |
| camera previews | `frames/<track>@preview/` | `-o DIR` |
| finished and base clips | `clips/` | `--clips DIR` |
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

Every shot and every caption of the project reads the `cameras.yml` at the root, so a
shot in `shots/` and a caption anchored to the model in `text/` share the same views and
tracks. The camera commands write there too, unless given `-c FILE`. A `cameras.yml` left
beside a shot below the root is an error, rather than being read or quietly ignored:

```text
Error: afms/shots/cameras.yml: a project has one cameras.yml, at its root; move this one
to afms/cameras.yml (merge their views and tracks if both exist)
```

Paths written inside files (a shot's `source`, a film shot's `frames`, a caption file)
are still relative to the file that holds them.

## Looking at a project, and cleaning it

```text
$ flowreel project info
project /home/a/films/afms
data:    run -> /scratch/afms/run
source:  vtk:../data/run/flow.pvd
bodies:  cylinder
shots:   2
  shots/reveal.yml: reveal, 288 frames drawn
  shots/wake.yml: wake, 0 frames drawn (25 in drafts)
cameras: views main, side; tracks approach
film:    film.yml: 4 shots, 41.5 s planned
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
| `flowreel.project.init.make_project(folder, source=None, ..., link=None)` | lays out the folder, returns what it wrote and kept |
| `flowreel.project.paths.find_root(start)` | the project root holding `start`, or `None` |
| `flowreel.project.paths.require_root(start)` | the same, or `NotInProject` saying how to make one |
| `flowreel.project.paths.cameras_file(start)` | the `cameras.yml` a file there uses |
| `flowreel.project.paths.output(start, "frames")` | `<root>/frames`, or beside `start` outside a project |
| `flowreel.project.info.info(root)`, `.clean(root, ["cache"], dry_run=False)` | `project info` and `project clean` |
