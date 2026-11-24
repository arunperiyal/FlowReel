# Cameras and lights

Code: `flowreel.scene.views`, `camera_path`, `camera_file`, `orbit`, `camera_import`,
`framing`, `lights`, `projection`.
Lengths are in the source's unit; angles in degrees.

## Views (`cameras.yml`)

A view is a flexflow camera frame, so a file written by `flexflow field render
--pick-camera` is a valid single view (named `main`).

| Key | Type | Default | Example |
|---|---|---|---|
| `name` | string, unique, required in `views:` | | `name: main` |
| `position` | `[x, y, z]` | required | `position: [-19, 13, -5]` |
| `focal` | `[x, y, z]`, not equal to `position` | required | `focal: [6, 0, 8.5]` |
| `up` | `[x, y, z]`, not parallel to the viewing direction | `[0, 1, 0]` | `up: [0, 0, -1]` |
| `view_angle` | vertical field of view, 0 to 180 | `30` | `view_angle: 40` |
| `parallel` | boolean | `false` | `parallel: true` |
| `parallel_scale` | half the frame height; required when `parallel` | `1` | `parallel_scale: 10.6` |

```yaml
views:
  - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
  - {name: top, position: [6, 40, 9.5], focal: [6, 0, 9.5], up: [0, 0, -1],
     parallel: true, parallel_scale: 10.6}
```

## Camera tracks

```yaml
tracks:
  carve:
    frames: 288          # optional length
    path: linear         # linear (default) or spline
    ease: smooth         # between neighbouring keys; any track easing, default smooth
    keys:
      - {frame: 0, view: carve_wide}
      - {frame: 218, view: carve_close, ease: hold}   # this key to the next
      - {frame: 241, view: carve_close}
      - {frame: 282, view: main}
```

| Key | Type | Default | Example |
|---|---|---|---|
| `frames` | whole number >= 1 | the last key's frame | `frames: 288` |
| `path` | `linear` or `spline` | `linear` | `path: spline` |
| `ease` | a track easing (`linear`, `smooth`, `in`, `out`, `in_out`, `hold`) | `smooth` | `ease: in_out` |
| `keys` | list of `{frame, view, ease}`; frames increasing; at least one | required | |
| `keys[].frame` | number | required | `frame: 218` |
| `keys[].view` | a view name | required | `view: carve_close` |
| `keys[].ease` | a track easing, for the segment from this key to the next | the track's `ease` | `ease: hold` |

A key's own `ease` lets one track hold still, then glide: above, the camera waits at
`carve_close` from frame 218 to 241 (`hold`) and then eases to `main`. In Python,
`build_track(views, [(0, "carve_wide"), (218, "carve_close", "hold"), ...])` makes the
same track.

Position, focal point, up vector, view angle and parallel scale blend between the two
neighbouring keys; before the first and after the last key the view is held. `spline` runs
position and focal point through all keys on a Catmull-Rom curve (smooth through the keys,
no overshoot control; add a key to tame a bend). A perspective and a parallel view cannot
blend, so the track switches at the later key. A shot uses it with `camera: {track: carve}`.

To pick a track's views by eye rather than type them, use the
[camera editor](camera-editor.md). The [camera commands](../commands.md#camera-commands)
(`camera path`, `orbit`, `import`, `project`, `preview`) call the functions below.

## Writing cameras.yml

The camera editor and the camera commands write `cameras.yml` with
`save_cameras(path, views, tracks)` (the whole file) or `update_cameras(path, views,
tracks)` (adds to the file, replacing views and tracks of the same names and keeping
the rest in order). The file comes out as you would type it: one view a line, each track
with its keys, numbers with the digits they need to read back the same.

Why the file is rewritten rather than edited: YAML has no way to keep comments through a
load and save without an extra library, and the views must stay exactly what the window
showed. So the file's first line says comments are not kept, and the file it replaces
is left as `cameras.yml.bak`. Keep notes in a separate file if you need them. The new
file is written beside the old one and moved into place, so a crash never leaves half a
file.

A track key's view must be one of the views written (found by its name, or else by being
equal to one); otherwise the file could not name it, and nothing is written.

## Orbits

`orbit(target, radius, frames, ...)` returns views and a track that circle a point; it
is what `camera orbit` writes.

| Argument | Type | Default | Example |
|---|---|---|---|
| `target` | `[x, y, z]`, model units | required | `(6, 0, 9.5)` |
| `radius` | number > 0, the camera's distance from the target | required | `12` |
| `frames` | whole number >= 2, the track's length | required | `240` |
| `azimuth` | degrees, where the orbit starts | `0` | `-30` |
| `span` | degrees turned, not 0; positive is anticlockwise seen from the axis tip | `360` | `120` |
| `elevation` | degrees above the plane across the axis, one value or `(from, to)`, each within 89 | `0` | `(10, 35)` |
| `axis` | `x`, `y`, `z` or a vector: what the camera turns about | `y` | `x` |
| `up` | vector, the camera's up | the axis | `(0, 1, 0)` |
| `lead` | model units: the focal point moved this far along the axis from the target | `0` | `1.5` |
| `view_angle` | degrees | `30` | `40` |
| `ease` | `linear`, `smooth`, `in`, `out`, `in_out`, over the whole orbit | `smooth` | `linear` |
| `name` | views are `<name>_00`, `<name>_01`, ... | `orbit` | `turn` |

Azimuth 0 is `+x` for the `y` and `z` axes and `+z` for the `x` axis. Keys lie evenly,
at most 5 degrees apart, on a `spline` path, so the camera keeps to the circle within
0.1% of the radius (the first and last segments sag most, since a spline repeats its end
keys; between the others it is within 0.0002%). Evenly, because a uniform spline
overshoots between keys spaced unevenly. A full turn is 73 views in `cameras.yml`. The ease is spread over the
whole turn, not per segment: key frames are placed where the eased motion reaches each
key, so a `smooth` orbit starts and stops gently without slowing at every key.

To circle a body, `body_target(source, body, station)` gives the body's centre at a
station along its axis (as `follow` finds it) and that axis. For an orbit round a
horizontal body, turn about its axis and give `up` across it:

```python
centre, axis = body_target(source, "riser", station=250.0)
views, track = orbit(centre, radius=8, frames=240, axis=axis, up=(0, 1, 0), span=180,
                     elevation=(15, 15), lead=2.0, name="riser_turn")
update_cameras("cameras.yml", views, {"riser_turn": track})
```

## Importing a view

`import_view(path, name, index=0, view=None)` reads one camera from another program's
file; it is what `camera import` writes.

| File | What is read |
|---|---|
| `.pvsm` | a ParaView state (*File > Save State*): the camera of render view `index` |
| `.py` | a ParaView Python state or trace: lines like `renderView1.CameraPosition = [...]`; the last assignment wins; render views counted in the order their camera is first set |
| `.yml`, `.yaml` | a flexflow camera frame (`--pick-camera`), or a `cameras.yml` (its only view, or `view`) |

ParaView, flexflow and FlowReel all use VTK's camera, so the numbers are taken as they
are and the view looks the same. A perspective view's `parallel_scale` is dropped, since
it does nothing.

## A shot's camera

The shot's `camera` mapping takes exactly one of `view`, `track` and `fit`; `follow` then
moves that view onto a body. Views and tracks are read from the project's one `cameras.yml`,
at its root, wherever the shot file is in the project ([projects](../projects/project.md)); outside a
project the library reads the one beside the shot file. A `cameras.yml` left beside a
shot below the root is an error that says to move it.

| Key | Type | Default | Example |
|---|---|---|---|
| `view` | a view name | | `camera: {view: main}` |
| `track` | a camera track name | | `camera: {track: carve}` |
| `fit` | `domain`, `crop` or `{x: [lo, hi], y: ..., z: ...}` | | `{fit: domain, direction_of: main}` |
| `direction_of` | a view name; with `fit`, required | | `direction_of: main` |
| `margin` | number > 0; with `fit` | `1.1` | `margin: 1.3` |
| `shape` | `picture` or `sphere`; with `fit` | `picture` | `shape: sphere` |
| `follow` | a body name (declared in the tag's `domain.yml`, or a zone of the source), or `true` for the one body | | `{view: close, follow: riser, station: 6}` |
| `station` | track, length unit along `axis`; with `follow`, required | | `{from: 2, to: 10, frames: [0, 120]}` |
| `axis` | `x`, `y` or `z`, the body's long axis; with `follow` | the body's declared `axis`, else its measured long axis, else `z` | `axis: x` |
| `motion` | boolean; with `follow` | `true` | `motion: false` |

With `motion: false` the centre is taken from the body at the shot's first frame, so the
camera keeps still while the body vibrates.

## Framing

- **`fit`**: `camera: {fit: domain, direction_of: main, margin: 1.1}` places the camera
  along a view's direction far enough to show a box, `margin` times as large. With
  `shape: picture` (the default) the box fills the shot's picture: its corners just in
  frame across or up, whichever is tighter for the shot's `size`, so a flat domain seen
  face on fills it, and a picture taller than wide still holds it. With
  `shape: sphere` the camera fits the box's bounding sphere instead, as FlowReel framed
  before Phase 8: spare room round the box, and the same distance whatever the view's
  direction, so a camera turning about the box keeps it whole. The sphere's angle is
  the view's vertical one, so in a picture narrower than it is tall it is cut at the
  sides. Perspective: the
  sphere's distance is `r*margin / sin(view_angle/2)`; parallel: `parallel_scale =
  r*margin`.
- **`follow`**: `camera: {follow: riser, station: 6.0}` puts the focal point on the
  body's centre at that station, keeping the view's direction and distance. The centre
  is the mean of the surface points within a slab of the station, along the body's axis
  (the declared `axis`, else its measured long axis, else `z`). The slab is a quarter of
  the declared diameter, else 2% of the body's length but no more than a quarter of its
  width, so a long body is cut thin. With `motion: false` the centre is taken from the
  body at rest, so a vibrating body stays visibly moving. `station` may be a track. The
  name is a body declared in the tag's `domain.yml` ([bodies](../projects/bodies.md)) or a
  zone of the source; `follow: true` takes the one body there is (the only declared one,
  else the source's only zone).

## Lights

A shot's `lights: default | raking | [list]`. Without the key the shot keeps VTK's own
light kit (a key light, fill lights and a headlight).

| Preset | Look |
|---|---|
| `default` | headlight 0.8 plus a soft fill 0.3 from above-left: even |
| `raking` | strong side light 1.0 along +x, weak headlight 0.15: grooves and ridges cast shading |

A list entry takes `kind` (`head` or `scene`, default `head`), `direction` (from the focal
point towards the light, for `scene`), `intensity` (default 1), `colour` (hex, default
white) and `specular` (default 0.3).

## Projection

`project(view, points, size)` returns the pixel `x` (right) and `y` (down from the top
left) of model points, and their depth in front of the camera. It matches VTK's own
projection, tested to 1e-6 px. Text and shape boxes that [follow a point](../film/layouts.md#follow-a-box-on-a-point-of-the-flow) use it.
