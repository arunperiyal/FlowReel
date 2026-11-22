# The film file

One YAML file, `film.yml`, describes the whole film: its shots in order, their rates,
freezes and fades, the words on them, the music and a watermark (plan Section 10). It
replaces the AFMS prototype's shot list in `make_film.py` and its `film_text.toml`.

This page covers the file, the captions and the timeline worked out from them. How
captions, shapes and the watermark are drawn is [captions](captions.md); cards are
[cards](cards.md); how each shot becomes a clip, at the film's rate with its text on
top, is [clips](clips.md); joining them into the film, with sound, a preview copy,
subtitles, chapters and a contact sheet, is [building the film](build.md). A runnable
example on generated frames, which prints a short film's timeline, is
`examples/film_timeline/run.py`.

```yaml
output: film.mp4
fps: 24
size: [1920, 1080]
include: style.yml                      # shared settings, see "Including files"
audio:
  - {file: assets/music.mp3, volume: 0.8, fade: [1.5, 4], licence: 'Pixabay Content License'}
watermark: {text: 'A. Periyal', corner: lower_right, size: 24, opacity: 0.6}
shots:
  - {name: opening, card: cards/opening.yml, seconds: 7, fade: [1.5, 1.5]}
  - {name: domain, frames: frames/bare_domain, fade: [1.5, 0], text: text/domain.yml}
  - name: compare
    layout: compare.yml
    rate: {fps: 8, to_output: interpolate}
    freezes: [{at: 5.0, hold: 6.0, text: text/freeze_motion.yml}]
  - {name: end, hold_last_of: compare, seconds: 13, fade: [0, 2], fade_out_at: 0.5}
```

Times are in **seconds of film** throughout (plan Section 3: frames count a shot's
pictures, steps are the solver's, seconds are the film's). Relative paths start at the
film file's folder.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `output` | path | `film.mp4` | the film written |
| `fps` | whole number | `24` | frames a second of the film |
| `size` | `[width, height]` | `[1920, 1080]` | pixels |
| `style` | mapping | below | fonts, colours, caption defaults |
| `audio` | a track, or a list of them | none | below |
| `watermark` | mapping | none | below |
| `shots` | list | required | the shots, in order |

## Shots

Each shot has a `name` (unique) and is one of four kinds:

| Kind | Key | Lasts |
|---|---|---|
| frames | `frames: FOLDER` (of `frame_NNNNN.png`, as `shot render` writes) | its frames at its rate, plus its freezes |
| layout | `layout: FILE` ([layouts](layouts.md)); its `rate: output` panels are drawn at the film's rate | as a frames shot, with the layout's frame count |
| card | `card: FILE` (a still card: [cards](cards.md)) | `seconds` |
| hold | `hold_last_of: SHOT` (the last frame of a frames or layout shot) | `seconds` |

| Key | Type | Default | Meaning |
|---|---|---|---|
| `seconds` | number | required for cards and holds | how long the still shows; not allowed on frames and layouts |
| `rate` | `{fps, to_output}` | `{fps: <film fps>}` | the shot's own frames a second, and how they are made up to the film's: `interpolate` (motion-compensated), `repeat` or `blend` |
| `freezes` | list of `{at, hold, text}` | none | stop on a frame for a while (below) |
| `fade` | `[in, out]` or one number | `[0, 0]` | seconds of fade from and to black |
| `fade_out_at` | number | so the fade ends with the shot | start the fade out early; what follows is black, so a caption can sit on it |
| `text` | a text file, or captions written in place | none | the shot's captions |
| `overlays` | bool | `true` | a hold of a layout shot: with its `rate: output` panels |
| `chapter` | `TITLE` or `{title, at}` | none | the shot starts a chapter, `at` seconds into the finished shot (`0`); see [chapters](build.md#chapters) |

**A shot's rate divides the film's.** `fps: 8` in a 24 frames a second film shows each
frame for three output frames (`to_output` says how they are made). The rate must
divide the film's, so live plots over a layout are drawn a whole number of times per
flow frame; `fps: 7` in a film of 24 is an error.

**Freezes.** `{at: 5.0, hold: 6.0}` stops the shot on the frame showing at 5 s of its
own frames, frame `round(5.0 * fps)`, and shows it for 6 s; everything after moves on
by 6 s. Freezes are listed in order of `at`. These are the rules of the AFMS film's
`make_film.py`, so a film rebuilt from its files has the same lengths.

## Captions

A shot's `text` (and a freeze's) is a list of captions, written in place or kept in a
text file of its own, so the person writing the words never edits `film.yml`:

```yaml
# text/domain.yml
- lines: ['Inlet', 'uniform flow, $U = 1$']
  at: [0.5, 6.5]
  place: [250, 575]
  size: 38
- lines: ['Each cycle sheds one vortex from each side']
  at: [8, {shot: bare_reveal, at: 2}]     # runs on across the cut
  box: true
  shapes:
    - {arrow: {from: [600, 858], to: [475, 745], width: 4}}
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `lines` | list of strings, or one | required | one string per line; `$...$` is mathematics |
| `at` | `[start, end]` or `start` | from 0 to the shot's end | seconds from the start of the finished shot, freezes included |
| `place` | `top`, `bottom`, `centre`, `[x, y]`, `[centre, y]` | `bottom` | `[x, y]` is the text's upper left corner in pixels; `[centre, y]` centres it across with its top at `y` |
| `size` | number | the style's (`50`) | letter height, pixels |
| `align` | `centre`, `left`, `right` | the style's (`centre`) | the lines against each other |
| `colour` | colour | the style's text colour | |
| `box` | bool | the style's (`false`) | a dark panel behind the text |
| `shadow` | bool | the style's (`true`) | a soft shadow behind the text |
| `fade` | number | the style's (`0.8`) | seconds to fade in and out |
| `shapes` | list | none | 2D shapes on the frame: `arrow`, `line`, `box`, `circle`, `ellipse`, `bracket`, `dimension`, `highlight` ([their keys](captions.md#shapes)) |
| `id` | string | none | a name for the caption, for other commands |

- **Times across a cut.** `end: {shot: NAME, at: S}` ends the caption `S` seconds into
  a later shot. An `end` past the shot's own end is an error, which says to do this,
  so a caption is never cut short without notice.
- **A freeze's captions** count from the start of the freeze. Left out, `at` is the
  freeze less 0.3 s at its start and 0.2 s at its end, as in the AFMS film.
- **Quote a line with a colon.** `Outlet: p = 0` unquoted is a mapping to YAML; the
  error says to write `'Outlet: p = 0'`. Single quotes also keep `$12D \times 30D$`
  as written.
- **Places in the model.** A caption's `place` and a shape's points may be points of
  the model, `{model: [x, y, z]}`, which follow the camera
  ([points in the model](captions.md#points-in-the-model)).

How captions are drawn (measured text, shadow or box, the shapes' keys) is on
[captions, shapes and the watermark](captions.md).

## Style

| Key | Type | Default | Meaning |
|---|---|---|---|
| `font` | string | `Lato` | the text's font family; the bundled Lato is always there |
| `maths` | `font`, `dejavusans`, `dejavuserif`, `cm`, `stix`, `stixsans` | `font` | maths in the text's own font (as the AFMS film), or a matplotlib maths font |
| `colours.text`, `colours.muted` | colour | `'#f2f2f2'`, `'#96a5b2'` | text, and quieter text (card headings) |
| `caption.size`, `.shadow`, `.box`, `.fade`, `.align` | | `50`, `true`, `false`, `0.8`, `centre` | defaults of the caption keys above |
| `caption.margin` | number | `80` | pixels from the edge for `top` and `bottom` |
| `caption.spacing` | number | `1.3` | line spacing, times the size |

## Audio

One track, or a list. Each has `file` (required), `offset` (seconds into the track to
start from, `0`), `start` (seconds into the film, `0`), `volume` (`1` as recorded),
`fade` (`[in, out]` seconds) and `licence` (a note kept with it). Music files stay out
of the repository.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `file` | path | required | the sound file, from the film file's folder |
| `offset` | seconds | `0` | where in the file to start playing |
| `start` | seconds | `0` | when in the film the track starts |
| `volume` | number | `1` | gain; `1` is as recorded |
| `fade` | `[in, out]` seconds | `[0, 0]` | fade in from the track's start, fade out to its end |
| `licence` | text | none | a note, not used |

The build measures every file's length rather than trusting a plan (the prototype's
planned and measured lengths differed by a second). A track plays until the picture
ends or the file runs out, whichever comes first, and its fade out ends there, so music
shorter than the film fades to silence instead of stopping. Tracks are added, not
averaged, so two tracks at `volume: 0.5` sound as one at `1`. Silence fills the rest of
the picture. An `offset` past the file's end, or a `start` after the picture's end, is
an error. `build(..., mute=True)` (`film build --mute`) leaves the sound out.

## Watermark

A signature, logo or watermark (plan Section 10.7): `image` (a file, kept outside the
repository) or `text`; `corner` (`lower_right` by default) or `place: [x, y]`; `size`
in pixels; `opacity` (`0.7`); `colour` for text; when: `shots: [names]` or
`seconds: [start, end]`, else throughout; `cards: true` to show it on cards too. It is
drawn with the text at the build, so changing it never re-renders a frame. A shot file
may have a watermark of its own, drawn into its frames. How both are drawn:
[captions, shapes and the watermark](captions.md#the-watermark).

## Including files

Any FlowReel YAML file (films, text, shots, layouts, panels, cameras, `flowreel.yml`)
may include others, so styles and text can be shared between films:

```yaml
include: styles/film.yml        # a mapping: its keys, under this file's own
size: [1280, 720]               # this file's keys win
```

In a mapping, `include` is a file or a list of files, each holding a mapping; they are
merged in order beneath the mapping's own keys, nested mappings key by key. In a list,
an entry that is only `{include: FILE}` is replaced by that file's entries:

```yaml
# text/compare.yml
- include: text/common.yml
- {lines: ['One more caption'], at: [2, 5]}
```

Includes may include others; a file that includes itself is an error. Paths start at
the including file's folder.

## The timeline: `film.timeline`

```python
from flowreel import film

t = film.timeline(film.load("film.yml"))
for s in t.shots:
    print(s.shot.name, s.start, s.length)       # film seconds
for c in t.captions:
    print(c.caption.lines[0], c.start, c.end)    # film seconds
print(t.length)
```

Frames and layout shots are counted from their folders (a layout from its tiles and
panels, without composing it); `timeline(f, counts={"compare": 121})` gives counts
instead. Every caption and freeze is checked against its shot's length, and errors
name the film file and the shot's key path. A placed shot's `positions(fps)` are its
output frames as positions among its own frames, between shown frames and still
through freezes, which [`compose.layout(output=...)`](layouts.md#panels-at-the-output-rate-rate-output)
takes to draw live plots.
