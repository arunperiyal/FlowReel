# Rendering and caching

A shot file becomes pictures in two ways:

```python
from flowreel.scene import render, render_frame

picture = render_frame("shots/reveal.yml", 16)          # one frame, (h, w, 3) uint8
report = render("shots/reveal.yml", jobs=8)            # every frame, to files
print(report.count("rendered"), report.count("skipped"))
```

Code: `flowreel.scene.rendering`, `backend`, `keys`, `cache`, `memory`. The commands
(`flowreel shot render`, `shot preview`, `shot memory`) come in the next branch and call
these functions. A runnable example on generated data is `examples/render_shot/run.py`.

## The source

`render` and `render_frame` open the shot's `source: adapter:location` themselves; a
relative location is taken from the shot file's folder, and `geometry:NAME` names a body.
A source that needs more options (a vtk source with a separate body file) is built in code
and passed as `source=`. With `jobs` processes the source is sent to each process, so it
must pickle (a class defined at the top level of a module does).

## Frames and folders

| Output | Where |
|---|---|
| frames at the shot's size | `<out>/<shot name>/frame_00000.png` |
| draft frames | `<out>/<shot name>@<W>x<H>/frame_00000.png` |
| frame keys | `.keys.json` in each frame folder |
| cached surfaces | `<out>/.cache/surfaces/` |

`out` defaults to `frames`. A frame file is written under a temporary name and renamed,
so a frame on disk is never half written, even when a render is stopped.

## Options of `render`

| Option | Type | Default | Example |
|---|---|---|---|
| `frames` | list of frame numbers (0-based) | all | `range(0, 120, 10)` |
| `source` | a source object | the shot's own | `sources.create("vtk", path=..., body=...)` |
| `views`, `tracks` | named views and camera tracks | `cameras.yml` beside the shot file | |
| `out` | folder | `frames` | `out="build/frames"` |
| `jobs` | whole number, frames drawn at once | `1` | `jobs=16` |
| `threads` | threads per job | `min(4, cores // jobs)`, at least 1 | `threads=2` |
| `backend` | `auto`, `osmesa`, `egl` or `x` | `auto` | `backend="egl"` |
| `force` | draw frames even when their key is unchanged | `false` | `force=True` |
| `scale` | draft: the shot's size times this | none | `scale=0.5` |
| `size` | draft: `(width, height)` in pixels | none | `size=(640, 360)` |
| `processes` | draw each frame in its own process | `true` | `processes=False` to debug |
| `progress` | called with each finished frame | none | `progress=print` |

`render_frame(shot, frame, source=None, *, views, tracks, size, scale, backend)` takes the
same meanings and draws in the calling process.

The result is a `RenderReport`: `folder`, `backend`, and `frames`, one `FrameResult` per
frame asked for (`index`, `path`, `status` of `rendered` or `skipped`, `seconds`,
`peak_bytes`).

## A process per frame

Every frame is drawn in a fresh process, `jobs` at a time. That is slower to start (each
process loads VTK, about a second) but memory stays flat: VTK and the readers do not give
all their memory back, so one long-lived process grows frame after frame until the
machine swaps. Memory per frame, not cores, then limits `jobs` (see below).

`threads` caps each job's threads (Mesa's software rasteriser, BLAS, OpenMP), so `jobs`
sets the load on the machine: 16 jobs of 1 thread, or 4 of 4, on 16 cores.

## Backend

With no display, VTK needs an off-screen OpenGL. `auto` takes **OSMesa** (Mesa's software
renderer) when `libOSMesa` is installed, otherwise **EGL** (a GPU without a display),
otherwise VTK's default window. OSMesa is the default because it needs nothing from the
machine and is the faster on many cores; EGL is what a GPU node offers. `x` draws an X
window off-screen and needs `DISPLAY`. A forced backend that is not installed fails
instead of quietly using another. `render_frame` chooses the same way as `render`, so a
frame drawn alone and in a render is the same picture.

The backends differ by a few grey levels on edge pixels (the reveal frame differs from the
golden frame by a mean of 0.08 grey levels under OSMesa and 0.06 under EGL), so the
backend is not part of a frame's key: switching it does not re-render a film.

## Frame keys: what is drawn again

Each frame has a key: a hash of everything that reaches its picture (plan Section 11).

- every layer's option values at that frame (tracks evaluated);
- the camera's view at that frame (position, focal point, up, angle, scale);
- the step, the source (the adapter and its options, with paths resolved against the
  shot file, so the same relative path in two folders is two sources), the crop;
- the size and modification time of every file read for that step (`Source.files`: the
  flow and body files, and the project's series files);
- the picture size, background, anti-aliasing and lights;
- FlowReel's code: a hash of its own source files.

A frame is skipped when its file exists and `.keys.json` holds the same key. So a change
to a track that only moves frames 40 to 60 re-renders those frames and no others,
and a new FlowReel version re-renders everything it drew. A step's file rewritten in
place (a re-run, a new export) re-renders the frames that show that step, and no others.
`force=True` draws every frame asked for. A source without `files` is keyed by its
options alone; render it with `force` after changing its data.

## Frozen shots contour once

A frozen shot (`time: {frozen: ...}`) shows one step in every frame, so its surfaces are
the same in every frame. The first frame contours each `iso` surface and stores it in
`<out>/.cache/surfaces/`; the others read it and never load the flow. The key is the
source (paths resolved), step, its files' sizes and times, crop, the surface's options (`field`, `level`,
`colour_by`, `wall_gap`, `gap_body`) and the code. A level that is a track gives one surface per distinct level.
In a render with several jobs, the first frame is drawn alone, so the other jobs read the
surface instead of all contouring it at once. Draft and full-size renders share the
cache. Moving shots are not cached: each frame shows another step.

## Draft size

`scale=0.5` (or `size=(W, H)`) draws the same shot with fewer pixels, for a quick look or a
small copy to share. The camera, view angle and anything in model units stay; options in
pixels (outline `width`, body `zero_width`) are scaled by the ratio of the heights, so lines
keep their weight. A scaled size is rounded to even numbers of pixels, as video encoders
need. Draft frames go to `<shot>@<W>x<H>/`, so they never mix with full-size frames or make
them look stale.

## Memory and jobs

```python
from flowreel.scene.memory import measure
print(measure("shots/reveal.yml", frame=0).text())
```

```
frame 0: peak 0.98 GB in 1.1 s
source estimate for one step: 0.01 GB
free memory 22.5 GB, 16 cores; measured with 4 threads
suggested jobs: -j 16
```

`measure` draws one frame in a fresh process, the way `render` does, and reads that
process's peak resident memory. It is measured, not estimated, because the peak includes
Python, VTK and the reader (about 0.7 GB before any data), which every job pays. The
suggested `jobs` is as many as fit in 80% of the free memory, and no more than the cores
(at `threads` per job when `threads` is given, else one each). Frame 0 is the default
because in a frozen shot it is the frame that contours. The reference film needed about
0.7 GB per bare frame and 2.2 GB per helical frame.
