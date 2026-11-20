# Captions, shapes and the watermark, drawn

Phase 4, branch 2. A caption written in a text file (see [the film file](film.md#captions))
becomes one transparent picture the size of the film, which the build lays over its
shot with its own fades (branch 4). The film's watermark is drawn the same way. This page
says how they are drawn, the keys of the 2D shapes, and the watermark of a shot file.

All positions and sizes are **pixels of the film**: `(0, 0)` is the upper left corner,
`x` to the right, `y` down. In a 1920 by 1080 film, `[960, 540]` is the centre.

## How a caption is drawn

```python
from flowreel import film
from flowreel.film.draw import caption_image

f = film.load("film.yml")
for c in f.shot("domain").text:
    image, block = caption_image(c, f.style, f.size)   # Pillow RGBA, and where the text is
    image.save(f"caption_{c.id}.png")
```

- **Text and maths by matplotlib.** Each line is set in the style's font (the bundled
  Lato), and `$...$` is mathematics. With `style.maths: font` (the default) the maths
  is in Lato too, upright, italic and bold, so `$C_L$` matches the words around it, as
  in the AFMS film. A matplotlib maths font set (`cm`, `stix`, ...) can be named instead.
- **Measured, not estimated.** Each line is measured after it is set, and placed by its
  measured width. Centring, `align` and the box therefore fit the text as drawn,
  maths included, and a longer line never runs past a box.
- **Places.** `top` and `bottom` are centred across the frame, `caption.margin` pixels
  (default 80) from the edge; `centre` is the middle of the frame; `[x, y]` puts the
  text's upper left corner there; `[centre, y]` centres it across with its top at `y`.
  Lines are `size × caption.spacing` pixels apart (default 1.3).
- **`align`** places the lines against each other inside the block: `left`, `centre`
  or `right`.
- **Shadow or box.** `shadow: true` (the default) puts a soft dark shadow behind the
  text and shapes: their outline, widened by 9 pixels and blurred by 12. It keeps light
  text readable on light flow without hiding the picture. `box: true` puts a dark panel
  (alpha 175 of 255, corners rounded by 12 pixels) behind the text instead, padded by
  0.6 of the letter size. When `box` is true, there is no shadow.
- **Size.** `size` is the letters' height in pixels (matplotlib's font size at 100 dots
  per inch, times 100/72), so a size of 50 reads the same in any film size's pixels.

These are the AFMS film's rules (`make_film.caption_image`). The test
`tests/test_golden_captions.py` draws two of its captions in both programs and finds no
pixel different.

`flowreel.film.draw.text_block(caption, style, size)` gives the same `Block` (the box,
each line's corner and measured width) without drawing, for code that needs to know
where text falls.

## Shapes

A caption's `shapes` is a list of 2D shapes, one per entry, written as `{kind: {keys}}`.
They are drawn on the caption's picture, so they fade in and out with it and share its
shadow. Each is in the caption's colour unless it gives `colour`.

```yaml
- lines: ['Each groove $0.08D$ deep and $0.2D$ wide']
  at: [8.4, 10.6]
  place: [1080, 50]
  box: true
  shapes:
    - {arrow: {from: [1250, 150], to: [1400, 400]}}
    - {dimension: {from: [1200, 900], to: [1500, 900], value: '$0.2D$', offset: 30}}
    - {highlight: {from: [1150, 380], to: [1650, 760], dim: 0.6, radius: 12}}
```

| Shape | Keys (required first) | Defaults | Draws |
|---|---|---|---|
| `arrow` | `from`, `to`; `width`, `head`, `colour` | `width: 4`, `head: 4.5 × width` | a line with a filled head at `to`, `head` pixels long and half as wide |
| `line` | `from`, `to`; `width`, `colour` | `width: 4` | a straight line |
| `box` | `from`, `to` (opposite corners); `width`, `radius`, `fill`, `colour` | `width: 4`, `radius: 0`, no fill | a rectangle, corners rounded by `radius` |
| `circle` | `centre`, `radius`; `width`, `fill`, `colour` | `width: 4`, no fill | a circle |
| `ellipse` | `centre`, `radii: [rx, ry]`; `width`, `fill`, `colour` | `width: 4`, no fill | an ellipse with its axes along `x` and `y` |
| `bracket` | `from`, `to`; `depth`, `width`, `colour` | `depth: 20`, `width: 4` | a square bracket: a back from `from` to `to`, with tips `depth` pixels long |
| `dimension` | `from`, `to`; `value`, `offset`, `width`, `head`, `size`, `colour` | `offset: 0`, `width: 2`, `head: 14`, `size: 0.8 × the caption's` | a measured length: a line with heads at both ends, moved `offset` pixels away with lines back to the ends, and `value` (text, `$...$` allowed) beside its middle |
| `highlight` | `from`, `to`; `dim`, `radius` | `dim: 0.6`, `radius: 0` | the picture darkened outside a box, by `dim` (0: not at all, 1: black) |

- **Which side.** A bracket's `depth` and a dimension's `offset` are measured to the
  **left of the direction from `from` to `to`**. For a shape drawn left to right, left
  is up: a bracket under a feature, drawn left to right, has its tips pointing up at
  it. A negative value goes the other way.
- **Points** are `[x, y]` in pixels. A point in the model (`{model: [x, y, z], view: V}`),
  which follows a moving camera, comes with the camera editor in Phase 6, as do the 3D
  shapes (`arrow3d`, `block`, ...).
- **Keys are checked when the text file is read**, so a misspelt key (`widht`) is an
  error naming the file and the key path, not a surprise at the build.
- Colours are names (`orange`) or `#rrggbb`; `fill` is a colour, or left out for none.
- A highlight is drawn beneath its own caption's text, shadow and box, so the words
  stay bright over the dimmed picture. It dims whatever lies under it, other captions
  showing at the same time included; put the caption holding it first.

## The watermark

A signature, logo or watermark (plan Section 10.7), at one of two levels. Its keys:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `image` | file | | a picture (PNG with transparency is best), kept **outside** the repository; it must exist |
| `text` | string | | a line of text in Lato; give `image` or `text` |
| `corner` | `upper_left`, `upper_right`, `lower_left`, `lower_right` | `lower_right` | 2% of the picture's height from the edges |
| `place` | `[x, y]` | | its upper left corner, instead of `corner` |
| `size` | number | `32` | pixels high: an image's height, or the text's font size (as a caption's `size`) |
| `opacity` | 0 to 1 | `0.7` | multiplies the image's own transparency |
| `colour` | colour | `'#f2f2f2'` | of text |
| `shots` | list of names | | film level only: show it on these shots |
| `seconds` | `[start, end]` | | film level only: show it between these film seconds |
| `cards` | bool | `false` | film level only: show it on cards too |

**Film level** (`watermark:` in `film.yml`). It is drawn at the build, with the
captions, so changing it never re-renders a frame. By default it shows on every shot
but cards. `flowreel.film.watermark.spans(watermark, timeline)` lists where it shows,
as `(shot, start, end)` in each shot's seconds, for the build to lay it on.

**Shot level** (`watermark:` in a shot file), for frames used outside a film:

```yaml
# shots/carve.yml
watermark: {text: 'A. Periyal', corner: lower_right, size: 28, opacity: 0.6}
```

It is drawn into each PNG frame after the screenshot. Its keys (and an image file's size
and modification time) are part of the frame's key, so changing it draws the frames
again; a shot without one keeps the keys it had. A draft (`shot render --scale 0.5`)
scales the watermark with the picture, so a draft looks like the full frame, smaller.
`shots`, `seconds` and `cards` are errors at this level: a shot's watermark is in every
frame.

## Example

`examples/film_captions/run.py` draws the captions of `text/captions.yml` (every place,
a box and a shadow, every shape, maths) and a text watermark over a generated picture,
and writes one PNG per caption and a still with all of them on it. It needs no data.
