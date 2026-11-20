# Clips: each shot encoded once

Phase 4, branch 4. Before the film is [joined](build.md), every shot becomes two clips in
`clips/` beside the film file:

- the **base clip**: the shot's picture alone, at the film's rate and size, exactly as
  long as [the timeline](film.md#the-timeline-filmtimeline) plans;
- the **finished clip**: the base clip faded in and out, with its captions, shapes and the
  film's watermark on top.

Each clip is kept under a name holding a key of everything that changes it, so a build
redoes only what changed. Changing a word of a caption rebuilds one finished clip in
seconds; the base clip under it, which may hold minutes of interpolation, is kept.

## ffmpeg

Clips are encoded by ffmpeg 5.1 or later, from conda-forge, in FlowReel's environment:

```bash
conda install -n flexflow_env -c conda-forge ffmpeg
```

FlowReel takes the file named by `FFMPEG`, else the `ffmpeg` beside the environment's
Python, else the one on the path, and checks its version, filters (`minterpolate`,
`xfade`, `fade`, `overlay`, `tpad`, `framerate`, `scale`) and the `libx264` encoder once.
An error names the file found. Other programs ship old copies that can come first on the
path (Tecplot 360's is ffmpeg 4.3); the environment's own copy is chosen before the path
for that reason. `ffprobe` comes from beside the ffmpeg found, or `FFPROBE`.

## Base clips

| Shot | Base clip |
|---|---|
| `frames` | its frames in the timeline's order (frozen frames repeated), brought to the film's rate |
| `layout` | the layout composed for its output frames: the flow brought to the film's rate, its `rate: output` panels laid on, one drawn frame per output frame |
| `card` | the [card](cards.md) drawn in the film's style and size, held for `seconds` |
| `hold_last_of` | the named shot's last frame (a layout's with its live panels as they end, unless `overlays: false`), held for `seconds` |

**Rates** (`rate: {fps, to_output}`). A shot at 8 frames a second in a 24 frames a
second film shows each frame for three output frames, made by `to_output`:

| `to_output` | ffmpeg | Use for |
|---|---|---|
| `interpolate` (default) | `minterpolate`, motion-compensated, scene-cut detection off | smooth flow |
| `repeat` | `fps` | frames redrawn each time (streamlines) that interpolation would smear |
| `blend` | `framerate` | a soft cross-fade between frames |

Output frame *j* shows position *j / 3* among the shot's frames, and the last frame is
held for its whole step, so a shot of *n* frames lasts *n / fps* seconds, frame for frame.
These positions are the ones a layout's live panels are drawn at
(`TimedShot.positions`), so a plot's dot moves with the flow under it.

`minterpolate` alone never outputs its last input frame: the prototype's interpolated
shots stopped one flow frame short and then ended early. FlowReel gives it the last frame
twice, so the motion reaches it.

**Size and colour.** Pictures are scaled to fit the film's `size` and centred on black
(none is cropped), then converted to BT.709, the colours players expect of HD video.
Every clip is encoded alike (H.264, yuv420p, the film's rate and time base), which is what
lets the film join them without re-encoding. Base clips use `-crf 10` (nearly lossless,
since they are encoded again with the text), finished clips `-crf 14 -preset slow`, as the
AFMS film did.

## Finished clips

1. **Fades on the picture.** `fade: [in, out]` fades the base clip from and to black; the
   fade out starts at `fade_out_at` when given. They act on the picture alone.
2. **Captions on top**, each [drawn](captions.md) as a transparent picture and shown from
   its start to its end, with its own fade (`fade`, default the style's 0.8 s, at most
   half its time on screen). Because the fades came first, a caption can sit on black.
   A caption running across a cut shows to the end of its first shot and from the start
   of the next without a fade at the cut.
3. **The film's watermark**, on the shots and seconds it [shows on](captions.md#the-watermark).

Captions are converted to BT.709 before they are laid on, so `'#ff0000'` stays red.

## Keys

| Clip | Key |
|---|---|
| base, frames or layout | each frame file's name, size and modification time; the order; the rate; each live panel's frames; the whole ffmpeg command |
| base, card or hold | the drawn picture's pixels and the command |
| finished | the base clip's key, the fades, every caption's settings and times, the style, the watermark and when it shows |

A key is a hash; the clip is `clips/<base|shot>_<name>_<key>.mp4`, and an older clip of
the same shot is removed when a new one is built. A frame redrawn in place changes its
size or time, so the clips that show it are rebuilt; a card file whose comment changed
draws the same picture, so nothing is. `force` rebuilds everything asked for.

## From Python

```python
from flowreel import film
from flowreel.film.clips import Clips

c = Clips(film.load("film.yml"))           # clips/ beside film.yml; force=True to rebuild
for s in c.line.shots:
    clip = c.finished(s.shot.name)
    print(s.shot.name, clip.frames, "built" if clip.built else "kept", clip.path)
```

`Clips(..., panels={"jobs": 8})` passes options to the drawing of live panels.
`c.last_frame(NAME)` is a shot's last frame as a picture. The `film build` command
(branch 6) runs this for every shot, then joins the clips ([building the film](build.md)).

## Example

`examples/film_clips/run.py` builds the clips of a small film from generated frames: a
card, a shot at 8 frames a second interpolated with a freeze and two captions, and a hold
with a closing line on black. It prints each clip's planned and measured frames.
