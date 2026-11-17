# Cameras and lights

Code: `flowreel.scene.views`, `camera_path`, `framing`, `lights`, `projection`.
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
      - {frame: 218, view: carve_close}
```

Position, focal point, up vector, view angle and parallel scale blend between the two
neighbouring keys; before the first and after the last key the view is held. `spline` runs
position and focal point through all keys on a Catmull-Rom curve (smooth through the keys,
no overshoot control; add a key to tame a bend). A perspective and a parallel view cannot
blend, so the track switches at the later key. A shot uses it with `camera: {track: carve}`.

## A shot's camera

The shot's `camera` mapping takes exactly one of `view`, `track` and `fit`; `follow` then
moves that view onto a body. Views and tracks are read from the `cameras.yml` beside the
shot file.

| Key | Type | Default | Example |
|---|---|---|---|
| `view` | a view name | | `camera: {view: main}` |
| `track` | a camera track name | | `camera: {track: carve}` |
| `fit` | `domain`, `crop` or `{x: [lo, hi], y: ..., z: ...}` | | `{fit: domain, direction_of: main}` |
| `direction_of` | a view name; with `fit`, required | | `direction_of: main` |
| `margin` | number > 0; with `fit` | `1.1` | `margin: 1.3` |
| `follow` | a body name (declared in `flowreel.yml`, or a zone of the source), or `true` for the one body | | `{view: close, follow: riser, station: 6}` |
| `station` | track, length unit along `axis`; with `follow`, required | | `{from: 2, to: 10, frames: [0, 120]}` |
| `axis` | `x`, `y` or `z`, the body's long axis; with `follow` | `z` | `axis: x` |
| `motion` | boolean; with `follow` | `true` | `motion: false` |

With `motion: false` the centre is taken from the body at the shot's first frame, so the
camera keeps still while the body vibrates.

## Framing

- **`fit`**: `camera: {fit: domain, direction_of: main, margin: 1.1}` places the camera
  along a view's direction far enough to show a box. It fits the box's bounding sphere
  (safe for any aspect, with some spare room) times `margin`. Perspective: distance
  `r*margin / sin(view_angle/2)`; parallel: `parallel_scale = r*margin`.
- **`follow`**: `camera: {follow: riser, station: 6.0}` puts the focal point on the body's
  centre at that station (mean of the surface points within a slab of the station, along
  the body's axis, default `z`), keeping the view's direction and distance. With
  `motion: false` the centre is taken from the body at rest, so a vibrating body stays
  visibly moving. `station` may be a track. The name is a body declared in the
  project's `flowreel.yml` ([bodies](bodies.md)) or a zone of the source; `follow: true`
  takes the one body there is (the only declared one, else the source's only zone).

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
projection, tested to 1e-6 px. Use it to place captions and arrows.
