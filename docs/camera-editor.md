# The camera editor

A window that shows a shot's scene and collects the views you pick into a camera track of
`cameras.yml`. It is the one window FlowReel has (plan Section 2): everything else is
files, and the editor's only output is a file too. Code: `flowreel.editor`.

The command, `flowreel camera edit SHOT.yml`, comes with the camera commands; until
then, open it from Python (below).

## Picking a track

1. Open the editor on a shot and a new track name.
2. Move the camera with the mouse as in any VTK window (left drag turns, right drag or
   the wheel zooms, middle drag pans).
3. Set the **Frame** slider to the frame the view belongs to, and press `s`.
4. Repeat for the other keys of the track. Press `p` to watch the track play.
5. Close the window. There is nothing to save: every change was written at once.

| Key | Button | Does |
|---|---|---|
| `s` | Save view | the camera's view becomes the track's key at the Frame slider's frame (a key already there is replaced) |
| `u` | Undo | goes back one change |
| `r` | Replace | the key nearest the Frame slider takes the camera's view, keeping its frame |
| `p` | Play | plays the track at 24 frames a second, then returns to the view you had |
| `n` | Next step | shows the next time step (the **Time step** slider does the same) |

VTK's own meaning of these four letters (`s` surface, `r` reset camera, `u` user event,
`p` pick) is switched off in the editor; VTK's other keys still work (`w` wireframe,
`q` quit, `f` fly to the point under the mouse).

The line at the top says how many views are saved, the frame and the step, and what the
last key did. The film's points in the model (captions and shapes [anchored](captions.md#points-in-the-model)
to the shot's frames) are shown as small yellow markers with their caption's first line,
so a view can leave room for the words.

## What is written

The track goes into `cameras.yml` under its name, its keys' views named
`<track>_<frame>` (`approach_0000`, `approach_0120`):

```yaml
views:
  - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
  - {name: approach_0000, position: [-24.1, 9.6, 2.2], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
  - {name: approach_0120, position: [-8.3, 3.1, 7.9], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
tracks:
  approach:
    frames: 240
    path: linear
    ease: smooth
    keys:
      - {frame: 0, view: approach_0000}
      - {frame: 120, view: approach_0120}
```

- **Written at once.** Each save, replace and undo rewrites the file, so closing the
  window, or a crash, loses nothing. The file is written by
  [`save_cameras`](cameras.md#writing-camerasyml): the old one is kept as
  `cameras.yml.bak`, and comments in it are not kept.
- **Other views and tracks stay** as they were. A track of the same name is taken up
  where it was left, with its keys and its `path`.
- **A view another track uses is never changed.** Saving over a key that uses one (say
  `main`) gives that key a view of its own instead.
- **Ease and path.** The track is written with the default `smooth` ease and `linear`
  path (or the path of the track taken up); change them, or a key's own `ease`, in the
  file afterwards.
- A shot then uses the track with `camera: {track: approach}`.

## The scene

The window shows the shot's layers as `shot render` draws them, at one time step at a
time. The first time a step is shown it is read and drawn (the status line says how long
it took); after that it is kept, so stepping back and forth is instant. A step is drawn
with the layer values of the first frame that shows it.

The Frame slider only says which frame the next view belongs to; it does not change the
scene. That is on purpose: a frozen shot shows one step through all its frames, and a
moving one would have to be read again at every frame.

## Away from the data (`--vtp`)

The data of a long case lives where it was computed, often a cluster with no display.
Save the scene's surfaces there, copy the folder, and pick the views on a laptop:

```bash
# where the data is: the surfaces of the steps that frames 0, 120 and 239 show
flowreel shot render riser.yml --frames 0,120,239 --save-vtp riser_vtp
# on the laptop
scp -r cluster:films/riser/riser_vtp .
```

`--save-vtp DIR` draws no frames. Each step goes to `DIR/step_<NNNNNNNN>/`, one `.vtp`
per surface with its colours baked in (RGBA, so no field or colour map is needed to open
it) and a `scene.json` of its look; `DIR/scene.json` holds the shot's first view,
background and stretch. Text and colour bars are not saved. The surfaces are for framing
a view: they look as they were drawn, though not to the last pixel (tested to within 2
grey levels of 255 on average).

## From Python

```python
from flowreel.editor.scenes import ShotScenes
from flowreel.editor.state import EditorState
from flowreel.editor.window import EditorWindow
from flowreel.film import load
from flowreel.film.anchors import anchors_for_frames
from flowreel.scene.rendering import Scene

scenes = ShotScenes(Scene.make("shots/riser.yml"))
# or, away from the data: from flowreel.editor.surfaces import SavedScenes
#                         scenes = SavedScenes("riser_vtp")
state = EditorState.open("cameras.yml", "approach", frames=240, steps=scenes.steps)
anchors = anchors_for_frames(load("film.yml"), "frames/riser")      # optional
EditorWindow(state, scenes, anchors=anchors).show()
```

`EditorWindow(..., off_screen=True)` makes a window that is never shown: drive it with
`press("s")`, `look(view)`, `set_frame(n)` and `set_step(i)`, as the tests and
`examples/camera_editor/` do.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `EditorState.open(path, track, frames, steps)` | | | the file, the track's name, its length in frames, the steps to show |
| `path_kind` | `linear` or `spline` | `linear` (or the track taken up's) | the track's `path` |
| `EditorWindow(state, scenes)` | | | the editor on a state and a scene source |
| `size` | `(width, height)` pixels | `(1280, 720)` | the window |
| `anchors` | list of `(name, (x, y, z))` | none | points to mark |
| `off_screen` | boolean | `false` | a window never shown, for scripts and tests |
