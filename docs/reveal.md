# The reveal look and its golden frame

The opening look of the AFMS film: a wake surface coloured by spanwise vorticity, and a
cutting plane that sweeps along the span, showing a live section of the flow while the
wake ahead of it is cut away and the rest turns grey.

It is an ordinary shot file on three layers, `tests/data/reveal/reveal.yml`, and a
golden-frame test checks it against the prototype's frame.

## The shot file

```yaml
time: {frozen: 5000, frames: 25}
camera: {view: main}                    # tests/data/reveal/cameras.yml
layers:
  - {type: body}
  - type: slice                         # the section
    normal: x
    position: &sweep {from: 4.1, to: 6.0, frames: [0, 24]}
    field: vorticity_x
    range: [-2.5, 2.5]
    opacity: {from: 0.0, to: 1.0, frames: [0, 2.4]}
    fade_weak: [0.05, 0.5]              # transparent where the flow is weak
    near_wall: [0.03, 0.1]              # and next to the body
  - type: iso                           # the wake
    field: lambda2
    level: -1.0
    wall_gap: 0.4                       # hides the sheath round the wall
    colour_by: vorticity_x
    range: [-2.5, 2.5]
    clip_axis: x
    clip_position: *sweep               # cut at the same plane
    clip_keep: above
    clip_active: {keys: [[0, false], [0.01, true]]}   # whole before the sweep starts
    grey: {from: 0.0, to: 1.0, frames: [9.6, 24]}
    grey_colour: "#6f8796"
```

The prototype drove everything from one "progress" number through smoothstep ramps; here
each ramp is its own track. The greying mixes colours in display values, not linear light,
as the prototype does, so that the pictures match. Layer options: `docs/layers-flow.md`.

```python
from flowreel.scene import render_frame
picture = render_frame("tests/data/reveal/reveal.yml", 16)   # (h, w, 3) uint8
```

## The golden-frame test

`tests/test_reveal_golden.py` draws `tests/data/reveal/reveal.yml` through `flowreel.scene.render_frame` and compares it with
`golden.png`, which the **prototype's own functions** drew from the same data. The
limits are a mean difference under 0.5 grey levels and under 0.2% of pixels differing by
more than 32; a frame two steps earlier in the sweep must fail them. The test is skipped
on a machine without off-screen OpenGL.

| File in `tests/data/reveal/` | What it is |
|---|---|
| `flow_5000.vti` | velocity of step 5000 of the cylinder case, sampled on a 21 x 41 x 61 grid in a box around mid-span |
| `body.vtp` | the part of the cylinder inside the box |
| `reveal.yml`, `cameras.yml` | the shot file and its view |
| `shot.yml` | the old key list, read only by `tools/make_reveal_data.py` to draw the golden frame with the prototype |
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
