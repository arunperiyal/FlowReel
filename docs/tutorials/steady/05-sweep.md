# 5. A second shot: a sweeping range

Almost every value in a shot may change along it: it is then a **track**, keys of
values at frames, rather than one value ([tracks](../../guide/shots/tracks.md)). The camera of the
first shot was one. In the second shot, the slice's colour range changes.

The vorticity is strong next to the wall and weak far from it. A range of ±60 shows the
shear layers and leaves the rest black. Narrow the range and the weak vorticity across
the domain comes up, while the strong part saturates. Sweeping the range shows both in
one shot.

Copy `shots/wake.yml` to `shots/sweep.yml` and change it to:

```yaml
name: sweep
source: crossflow
time: {frozen: 0, frames: 72}         # 3 s at 24
camera: {fit: {x: [0, 15], y: [-2.1, 2.1], z: [-0.05, 0.05]}, direction_of: approach_0000}
layers:
  - type: slice
    normal: z
    position: 0.0
    field: vorticity_z
    range: {from: [-200, 200], to: [-5, 5], frames: [12, 60], ease: in_out}
  - {type: body, body: cylinder}
```

- **`range: {from: ..., to: ..., frames: [12, 60]}`** is a track: ±200 until frame 12,
  then easing to ±5 by frame 60, and held there to the end. `ease: in_out` starts and
  ends the change gently. Other ways to write a track, with keys at several frames, are
  in [tracks](../../guide/shots/tracks.md#forms).
- **`camera: {fit: ..., direction_of: approach_0000}`** holds the camera still, looking
  the way of the first view you picked in chapter 4, as close as it can while the
  region `x` 0 to 15, `y` ±2.1 fills the picture: the wake, wide and low. The film will
  show this shot in a strip across half its frame (chapter 8), which this region fits
  ([cameras](../../guide/shots/cameras.md)). A view of `cameras.yml` can also be used on
  its own, `camera: {view: approach_0000}`.
- **`{type: body, body: cylinder}`** is the same layer written on one line; YAML allows
  either.

```text
$ flowreel shot preview shots/sweep.yml --every 12
```

![The sweep at frames 0, 48 and 71](images/05-sweep.png)

At ±200, only the layers on the wall show. At ±5, the weak vorticity carried away from
the cylinder fills the wake and spreads across the domain.

Next: [a panel](06-panel.md).
