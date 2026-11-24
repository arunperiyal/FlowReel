# Boxes

What a box shows is under one key, its kind, written short (`text: 'Hello'`) or as a
mapping of the kind's options. Where and when it shows are the box's own keys
([layouts and boxes](layouts.md#boxes)).

## `text`

Short: a line, or a list of lines. `$...$` is mathematics.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `text.lines` | a line or a list | required | the text |
| `text.look` | `title`, `text`, `small` | `text` | the look it starts from |
| `text.size`, `.colour`, `.weight`, `.align`, `.valign`, `.spacing`, `.shadow`, `.box`, `.fade`, `.margin` | as a look's | the look's | change the look for this box |
| `text.subtitle` | true or false | `true` | a timed text box (one with `at`) is a subtitle in `film.srt` |

## `image`

Short: the picture's file.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `image.file` | path | required | the picture; keep logos in `assets/`, outside FlowReel |
| `image.fit` | `contain`, `cover`, `stretch` | `contain` | all of it in the box; the box filled, cut to fit; or stretched |
| `image.opacity` | 0 to 1 | `1` | |

## `shape`

Short: the kind. A shape is drawn in its box, so it is placed like any box.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `shape.kind` | `line`, `arrow`, `rectangle`, `circle` | required | a rectangle is the box's outline, a circle the ellipse in it, a line or arrow crosses it |
| `shape.direction` | `right`, `left`, `up`, `down`, `up_right`, `up_left`, `down_right`, `down_left` | `right` | a line or arrow: from the middle of one side (or a corner) to the opposite one |
| `shape.colour` | colour | the text colour | |
| `shape.width` | pixels | `4` | the line's width |
| `shape.head` | pixels | `18` | an arrow's head |
| `shape.fill` | colour | none | inside a rectangle or circle; `#rrggbbaa` for see-through |
| `shape.radius` | pixels | `0` | a rectangle's rounded corners |
| `shape.shadow` | true or false | `false` | a soft shadow, as text has: an arrow over a picture stays readable |

A divider is a `line` box a few pixels high. An arrow to a point of the flow is an arrow
box with `follow`.

## `shot`

Short: the shot file. Its frames are the shot's, under `frames/<its name>`. Shots are
rendered beforehand (`shot render`, or on Slurm).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `shot.file` | path | required (or `frames`) | the shot file |
| `shot.frames` | folder | none | frames drawn elsewhere, instead of a shot file |
| `shot.rate` | `{fps, to_output}` | the film's rate | `fps`: the shot's frames a second, which divide the film's; `to_output`: `interpolate`, `repeat` or `blend` ([rates](../making/build.md#rates)) |
| `shot.freezes` | list of `{at, hold}` | none | stop at `at` seconds of the shot's frames for `hold` seconds; the other boxes go on |
| `freezes.at` | seconds | required | when, in seconds of the shot's own frames |
| `freezes.hold` | seconds > 0 | required | how long the frame is held |

## `panel` and `last_frame`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `panel.file` | path | required | a panel file; the build draws it at the box's size, at the film's rate |
| `panel.rate` | `{fps}` | the film's rate | its frames a second (its `times` in order); the build draws every output frame at the time between two frames, so a panel is never interpolated |
| `panel.freezes` | list of `{at, hold}` | none | as a shot's |
| `last_frame` | a scene's name | required | that scene's last frame, held (give the scene `seconds`) |

## Examples

- `examples/text_boxes/run.py DIR`: a title, a logo, a divider, text with maths and in a
  box, an arrow, a circle, an ellipse and a rounded rectangle over a picture, drawn as one
  still by `scene preview`.
- `examples/anchored_caption/run.py DIR` (needs ffmpeg): a text and an arrow that follow
  the sphere of a panning shot (`follow`).
