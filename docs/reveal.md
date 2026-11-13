# The reveal look and its golden frame

`flowreel.reveal` draws the opening look of the AFMS film: a wake surface coloured by
spanwise vorticity, and a cutting plane that sweeps along the span, showing a live
section of the flow while the wake ahead of it is cut away and the rest turns grey.

It is the first path through all of Phase 1: a **source** gives velocity and the body,
the **fields** give lambda2 and vorticity, and **tracks** drive the plane, the section's
opacity and the greying. In Phase 2 the wake, the section and the body become scene
layers and this module becomes a shot file.

## Drawing a frame

```python
from flowreel.reveal import reveal_frame, render_shot
picture = render_shot("tests/data/reveal/shot.yml")          # (height, width, 3) uint8
picture = reveal_frame(source, step=5000, frame=16, sweep={"from": 0.02, "to": 6.0,
                       "frames": [0, 24]}, camera=[(-19, 13, -5), (6, 0, 8.5), (0, 1, 0)])
```

## Shot file

| Key | Type | Default | Meaning |
|---|---|---|---|
| `source` | mapping | required | `adapter` and the adapter's options; `path` and `body` are relative to the file |
| `step` | integer | required | the saved step drawn |
| `frame` | number | required | the frame the tracks are read at |
| `size` | `[width, height]` | `[1920, 1080]` | pixels |
| `camera` | three vectors | required | position, focal point, view up |
| `view_angle` | number | `30` | vertical field of view, degrees |
| `wake.field`, `wake.level` | text, number | `lambda2`, `-1.0` | the wake surface; lambda2 is negative inside vortices |
| `wake.wall_gap` | number | `0.4` | wake nearer than this to the body is hidden (length unit) |
| `colour.field`, `colour.range` | text, pair | `vorticity_x`, `[-2.5, 2.5]` | what colours the wake and the section; the map is black at the middle |
| `muted` | colour | `"#6f8796"` | the colour the wake turns to |
| `axis` | `x`, `y` or `z` | `x` | the direction the plane travels along |
| `sweep` | track | required | the plane's position along `axis` |
| `slice_strength` | track | `1.0` | opacity of the section, 0 to 1 |
| `grey` | track | `0.0` | how far the wake has turned to `muted`, 0 to 1 |

Tracks are written as in `docs/tracks.md`. The prototype drove everything from one
"progress" number through smoothstep ramps; here each ramp is its own track, so the
section can fade in and the wake turn grey at any frames:

```yaml
sweep: {from: 4.1, to: 6.0, frames: [0, 24]}
slice_strength: {from: 0.0, to: 1.0, frames: [0, 2.4]}     # prototype: ramp(progress, 0, 0.1)
grey: {from: 0.0, to: 1.0, frames: [9.6, 24]}              # prototype: ramp(progress, 0.4, 1)
```

Before the sweep's first key the wake is whole; after it the wake is cut at the plane.
The section is transparent where the vorticity is weak and within 0.1 of the body. The
greying mixes the colours as the prototype does (in display values, not linear light),
so that the pictures match.

## The golden-frame test

`tests/test_reveal_golden.py` draws `tests/data/reveal/shot.yml` and compares it with
`golden.png`, which the **prototype's own functions** drew from the same data. The
limits are a mean difference under 0.5 grey levels and under 0.2% of pixels differing by
more than 32; a frame two steps earlier in the sweep must fail them. The test is skipped
on a machine without off-screen OpenGL.

| File in `tests/data/reveal/` | What it is |
|---|---|
| `flow_5000.vti` | velocity of step 5000 of the cylinder case, sampled on a 21 x 41 x 61 grid in a box around mid-span |
| `body.vtp` | the part of the cylinder inside the box |
| `shot.yml` | the shot |
| `golden.png` | 640 x 360, drawn by the prototype |

The data is coarse and does not follow the wall: it tests the picture, not the physics.
`tools/make_reveal_data.py CASE_DIR` remakes all of it from solver output; it sets the
prototype's sweep ends to the shot's, because the box is shorter than the span, and
changes nothing else of the prototype.

**Measured:** on the test data 0.02% of pixels differ at all, the largest by 13 of 255.
On the full step 5000 at 1920 x 1080, against the frame `render_frames.py --look reveal`
drew, 0.04% differ, the largest by 18 (a one-off check; the full files are not in the
repository). FlowReel took 4.5 s for that frame and the prototype 13 s, mainly because
the adapter reads only velocity.
