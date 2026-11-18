# Commands

`flowreel` is one program with two ways in:

- **one-shot:** `flowreel shot render carve.yml -j 16` runs one command and exits, as a
  script or a Slurm job needs;
- **interactive:** `flowreel` alone starts FlowReel's shell, with history, Tab completion
  and contexts, for the back-and-forth of building a shot.

`python -m flowreel ...` is the same, where the `flowreel` script is not on the path.

The commands are a thin layer over library functions (`flowreel.scene.render`,
`flowreel.scene.memory.measure`, `flowreel.scene.template.template`), so everything here
can also be done from Python; [rendering](rendering.md) explains what those do. A runnable
example on a shot that needs no data is `examples/shot_commands/run.sh`. The
command layer is [shellkit](https://github.com/arunperiyal/shellkit).

## The shell

```text
╭─ ~/films/afms [shot:carve.yml]
╰─❯ shot preview; shot render -j 16
```

`use shot:carve.yml` sets the shot; commands that take a shot then use it when you leave
it out, and print `Using shot: ...`. `unuse shot` clears it. `help`, `help shot`, and
`shot render --help` show the help. Commands can be chained with `;`, and the output of
one piped to the system's commands with `|`. `-d` (or `set debug on`) shows the full
traceback when a command fails.

## `shot render`

```text
flowreel shot render [SHOT] [--frames SPEC] [--scale S | --size W H] [--force]
                     [-j N] [--threads T] [--backend B] [--no-memory-check] [-o DIR]
```

Renders the shot's frames to `DIR/<shot>/frame_00000.png`. Frames whose key did not
change since they were drawn are skipped (see [rendering](rendering.md#frame-keys-what-is-drawn-again)).

| Option | Default | Meaning |
|---|---|---|
| `SHOT` | the `shot` context | the shot file |
| `--frames SPEC` | all | `A`, `A:B` (A to B, both included), `A:B:E` (every E-th), or a comma list: `0:10,24,40:120:20` |
| `--scale S` | none | a draft at the shot's size times S, rounded to even pixels |
| `--size W H` | none | a draft at W x H pixels |
| `--force` | off | draw the frames even when their key did not change |
| `-j N`, `--jobs N` | 1 | frames drawn at once, each in its own process |
| `--threads T` | `min(4, cores / N)` | threads per job |
| `--backend B` | `auto` | `auto` (OSMesa, else EGL), `osmesa`, `egl` or `x` |
| `--no-memory-check` | off | draw even if the jobs look too big for the free memory ([long bodies](long-bodies.md#memory)) |
| `-o DIR`, `--out DIR` | `frames` | folder of the frame folders |

Drafts go to `DIR/<shot>@<W>x<H>/` and never mix with the full-size frames. Each frame is
reported as it finishes, then a summary:

```text
  frame_00000.png rendered 1.2 s
  frame_00008.png skipped
2 rendered, 1 skipped in 6.8 s -> frames/reveal (backend osmesa)
```

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
free memory and cores of this machine, and the number of jobs that fit (80% of the free
memory, at most one per core, or cores / T with `--threads T`):

```text
frame 0: peak 0.98 GB in 1.1 s
source estimate for one step: 0.01 GB
free memory 22.5 GB, 16 cores; measured with 4 threads
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

## `project init`

```text
flowreel project init SOURCE [--body FILE] [--step N] [-o DIR] [--force]
```

Writes `DIR/flowreel.yml` with one body per surface zone of `SOURCE`, each under its
zone's name. A zone at least 3 times longer in one direction than across becomes a beam
body, with its `axis` and `diameter` measured from the surface; other zones get neither. The supports
and series are written commented out, to fill in: the files do not say how a body is
held, and a guess would be drawn as if it were known. See [bodies](bodies.md).

| Option | Default | Meaning |
|---|---|---|
| `SOURCE` | | `adapter:location`: `flexflow:CASE`, `vtk:flow.pvd`, `geometry:NAME` |
| `--body FILE` | none | body file or pattern, for a source that reads it separately (`vtk`) |
| `--step N` | the first | step whose surfaces are measured |
| `-o DIR`, `--out DIR` | `.` | project folder |
| `--force` | off | overwrite an existing `flowreel.yml` |

```text
$ flowreel project init geometry:grooved_cylinder -o carve
wrote carve/flowreel.yml: 1 body (grooved_cylinder); fill in the supports
```

## Errors and exit status

A problem in a shot file is reported with the file and key path, and the nearest valid
key when there is a typo; no traceback:

```text
Error: carve.yml: sise: unknown key 'sise' (allowed: ...); did you mean 'size'?
```

The exit status is 0 on success, 2 for a wrong option or shot file, 1 for any other
failure, and 130 when stopped with Ctrl-C.
