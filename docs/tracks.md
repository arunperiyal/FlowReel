# Tracks

A **track** is a value that may change with the frame number: an opacity, a camera
position, a colour, the simulation step to show. Any option of a shot that accepts a track
can be written as a fixed value or as keys, so nothing is animated in code. Tracks live in
`flowreel.tracks`.

```yaml
opacity: 1.0                                           # fixed
position: {from: 0.02, to: 6.0, frames: [48, 72]}      # two keys, eased
grey: {keys: [[0, 0], [58, 0], [72, 1]]}               # any number of keys
level: {keys: [[0, -0.1], [120, -1.0]], ease: out}
```

Frames are the shot's own frame numbers, starting at 0. They may be fractional.

## Forms

| Form | Written as | Meaning |
|---|---|---|
| fixed | `opacity: 1.0` | the same value on every frame |
| two keys | `{from: a, to: b, frames: [start, end]}` | `a` up to `start`, `b` from `end`, eased between |
| keys | `{keys: [[frame, value], ...]}` | the value at each listed frame, eased between neighbours |

The two-key form is short for `{keys: [[start, a], [end, b]]}`.

## Keys of a track

| Key | Type | Default | Example |
|---|---|---|---|
| `from` | a value | required in the two-key form | `from: 0.02` |
| `to` | a value of the same type | required in the two-key form | `to: 6.0` |
| `frames` | `[start, end]`, with `start < end` | required in the two-key form | `frames: [48, 72]` |
| `keys` | list of `[frame, value]`, frames strictly increasing | required in the keys form | `keys: [[0, 0], [58, 0], [72, 1]]` |
| `ease` | one of the easings below | `smooth` (`linear` for `time`; `hold` for booleans and choices) | `ease: out` |

`keys` cannot be combined with `from`, `to` or `frames`. Any other key is an error.

## Value types

The type is taken from the values; every key of one track must have the same type.

| Type | Written as | Between keys | `at()` returns |
|---|---|---|---|
| number | `1.0`, `-3` | interpolated | `float` |
| vector | `[0, 2.5, 6]` (any length, the same at every key) | interpolated, component by component | tuple of `float` |
| colour | `"#rrggbb"`, `"#rgb"`, or `[r, g, b]` with each in 0..1 | blended in linear RGB | sRGB tuple `(r, g, b)`, each in 0..1 |
| boolean | `true`, `false` | steps | `bool` |
| choice | any other text, e.g. `viridis` | steps | `str` |

- **Colours** are stored as sRGB. To blend two of them they are decoded to linear light,
  interpolated, and encoded as sRGB again. Blending the sRGB numbers directly makes the
  middle of a fade too dark; halfway from black to white is `0.7354` in sRGB, not `0.5`.
- **Quote hex colours** in YAML (`colour: "#96a5b2"`): an unquoted `#` starts a comment.
- **RGB lists are 0..1, not 0..255.** A list of numbers is read as a vector unless the
  option is a colour; code that reads a colour option passes `kind="colour"` to `parse`.
- **Booleans and choices cannot be interpolated.** They keep a key's value until the
  frame of the next key, then switch. Their only ease is `hold`; any other is an error.

## Easing

The ease shapes the move between two neighbouring keys. With `t` the fraction of the way
from one key to the next (0 to 1):

| `ease` | Formula | Use |
|---|---|---|
| `linear` | `t` | constant rate |
| `smooth` | `3t^2 - 2t^3` (smoothstep) | starts and ends gently; the default |
| `in` | `t^3` | starts slowly, ends at full rate |
| `out` | `1 - (1 - t)^3` | starts at full rate, settles slowly |
| `in_out` | `4t^3` for `t < 0.5`, else `1 - (2 - 2t)^3 / 2` | slow at both ends, faster than `smooth` in the middle |
| `hold` | `0` until `t = 1` | steps: keeps the earlier value until the next key |

**Default: `smooth`.** The prototype eased every move with smoothstep, and the design calls
the two-key form "eased" without naming an ease, so a track with no `ease` moves the way
the prototype's shots did. One `ease` applies to every interval of the track.

The exception is `time` (below), whose default is `linear`.

## Clamping

Before the first key a track holds the first value; after the last key it holds the last.
A track never extrapolates.

```yaml
grey: {keys: [[58, 0], [72, 1]]}    # 0 on frames 0 to 58, 1 from frame 72 on
```

## Time as a track

```yaml
time: {keys: [[0, 5000], [120, 5300]]}   # step 5000 at frame 0, step 5300 at frame 120
time: 5000                               # the flow frozen at step 5000
```

The `time` track maps a frame to a simulation step. Fields are never interpolated between
saved steps: the frame shows the **nearer saved step**.

- **Tie rule:** a frame that asks for a step exactly halfway between two saved steps shows
  the **earlier** one, so a frame never shows the flow later than the time asked for.
  With steps saved every 50, frame 10 above asks for step 5025 and shows 5000.
- **Outside the saved range** the first or last saved step is shown.
- **Default ease: `linear`**, unlike other tracks, so that flow time advances at a
  constant rate. Write `ease: smooth` (or another) to slow the flow in or out.
- If steps are saved more sparsely than the frames ask for, neighbouring frames show the
  same step.

## In Python

```python
from flowreel.tracks import parse, TimeTrack

grey = parse({"keys": [[0, 0], [58, 0], [72, 1]]}, name="grey")
grey.at(65)        # 0.5
grey(100)          # 1.0, clamped; calling a track is the same as .at()
grey.fixed         # False

colour = parse({"from": "#000000", "to": [1, 1, 1], "frames": [0, 2]}, kind="colour")
colour.at(1)       # (0.7353..., 0.7353..., 0.7353...)

time = TimeTrack({"keys": [[0, 5000], [120, 5300]]})
time.at(60)                        # 5150.0, the step asked for
time.step(60, source.steps())      # the nearer saved step
```

| Name | Does |
|---|---|
| `parse(spec, kind=None, name="track", default_ease="smooth")` | builds a `Track`; `kind` forces the value type, `name` starts every error message |
| `Track.at(frame)` / `Track(frame)` | the value at a frame |
| `Track.fixed` | true when the value is the same on every frame (useful for caching) |
| `Track.frames`, `.values`, `.ease`, `.kind`, `.name` | the parsed keys |
| `TimeTrack(spec, name="time")` | the time track; `.at(frame)` and `.step(frame, steps)` |
| `nearest_step(value, steps)` | the saved step nearest to `value`, earlier on a tie |
| `ease(name, t)` | an easing by name, `t` clamped to 0..1 |
| `blend(kind, a, b, t)` | the value a fraction `t` of the way from `a` to `b` |
| `parse_colour(value)` | hex string or RGB list to an sRGB tuple in 0..1 |
| `srgb_to_linear(c)`, `linear_to_srgb(c)` | the sRGB transfer functions, per channel |
| `EASE_NAMES`, `KINDS`, `DEFAULT_EASE` | the allowed easings and types |

## Errors

A malformed track raises `ValueError`; the message starts with the track's name and names
the bad key, so it can be shown as it is:

```
grey: frames in 'keys' must increase, but 58 follows 72
grey: frame 58 appears twice in 'keys'
grey: unknown ease 'bounce' (allowed: linear, smooth, in, out, in_out, hold)
grey: unknown key 'easing' (allowed: from, to, frames, keys, ease)
grey: missing key 'to'; the two-key form needs from, to and frames
grey: mixed value types (number and choice); every key needs the same type
visible: ease 'linear' cannot be used with boolean values; they step from key to key (ease: hold)
```
