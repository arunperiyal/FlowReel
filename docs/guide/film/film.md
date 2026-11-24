# The film

A film is described in **levels**: the film, its scenes, each scene's layout, and the
layout's boxes. Each box shows one thing: text, a picture, a shape, a shot's frames, a
panel, or another scene's last frame.

```text
film            film.yml
├── properties  output, fps, size, style
├── audio
├── watermark
└── scenes      each: a layout, a length, fades or a cross-fade, a chapter
    └── layout  in film.yml, or layouts/NAME.yml
        └── boxes: text, image, shape, shot, panel, last_frame
```

**Why levels.** A film used to be made of seven kinds of thing: film shots of four kinds
(`frames`, `layout`, `card`, `hold_last_of`), layout files of tiles, card files and
caption files. Each had its own keys, and a caption over a layout needed three of them.
The levels need three nested ones. A title card is a scene of text and image boxes, a
plain shot is a scene of one box, and a caption is a text box timed in its scene.

`flowreel film template --scenes` writes a film of scenes with every key, and `--layout` a layout file.
This page is the film level; [layouts](layouts.md) places boxes, [boxes](boxes.md) is each kind of box, and
[building the film](../making/build.md) makes it.

```yaml
output: film.mp4
fps: 24
size: [1920, 1080]
style: {font: Lato, looks: {title: {size: 64}}}
scenes:
  - name: opening                          # a title card
    seconds: 6
    fade: [1.5, 1.5]
    chapter: Opening
    layout:
      boxes:
        - {image: assets/logo.png, pos: [810, 100], size: [300, 190]}
        - {text: {lines: ['Helical grooves'], look: title}, place: centre}
  - name: reveal                           # a shot: a scene of one box
    layout:
      boxes:
        - shot: shots/reveal.yml
        - {text: ['$Re = 1000$'], place: bottom, at: [1, 6]}
    cross: 1.0
  - name: compare
    layout: compare                        # layouts/compare.yml
  - name: end
    seconds: 8
    fade: [0, 2]
    layout: {boxes: [{last_frame: compare}]}
```

## The film's keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `output` | path | `film.mp4` | the film, from the film file's folder |
| `fps` | integer | `24` | frames a second of the film |
| `size` | `[width, height]` | `[1920, 1080]` | the film's pixels; boxes are placed in them |
| `style` | mapping | the defaults below | fonts, colours and the looks of text |
| `audio` | list | none | sound tracks ([below](#audio)) |
| `watermark` | mapping | none | a signature or logo ([below](#the-watermark)) |
| `scenes` | list | required | the scenes, in order |

### Style

| Key | Type | Default | Meaning |
|---|---|---|---|
| `style.font` | font family | `Lato` (bundled) | the text's font |
| `style.maths` | `font` or a maths font set | `font` | the font of text between `$` |
| `style.colours` | `{text, muted}` | below | the film's two colours |
| `style.colours.text` | colour | `#f2f2f2` | text and shapes, unless a box says |
| `style.colours.muted` | colour | `#96a5b2` | the `small` look, and `colour: muted` |
| `style.looks` | mapping of `title`, `text`, `small` | below | how text looks; a text box starts from one |

A **look** has these keys. The defaults are `title` (size 64, no shadow, no fade),
`text` (the values in the table: a caption's look) and `small` (size 26, muted, no
shadow, no fade).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `looks.size` | number > 0 | `50` | letter height, pixels |
| `looks.colour` | colour, `muted` or `~` | `~`: the text colour | the letters' colour |
| `looks.weight` | `regular`, `light`, `bold`, `italic` | `regular` | the font's weight |
| `looks.align` | `centre`, `left`, `right` | `centre` | the lines against each other |
| `looks.valign` | `top`, `centre`, `bottom` | `centre` | the text in its box |
| `looks.spacing` | number > 0 | `1.3` | line spacing, times the size |
| `looks.shadow` | true or false | `true` | a soft shadow behind the letters |
| `looks.box` | true or false | `false` | a dark box behind the text |
| `looks.fade` | seconds | `0.8` | in and out, unless the box gives `fade` |
| `looks.margin` | pixels | `40` | from the box's edges |

## Scenes

| Key | Type | Default | Meaning |
|---|---|---|---|
| `scenes.name` | string | required | unique; `last_frame` and the watermark name it |
| `scenes.layout` | mapping, or a name | required | the layout in place, or `layouts/NAME.yml` (a path ending `.yml` is taken from the film file's folder) |
| `scenes.seconds` | seconds | its main box's length | how long a scene of text, pictures or a held frame lasts |
| `scenes.fade` | seconds, or `[in, out]` | `[0, 0]` | from and to black |
| `scenes.cross` | seconds | `0` | dissolve into the next scene; not with a fade out, not on the last scene |
| `scenes.chapter` | title, or `{title, at}` | none | starts a chapter ([chapters](../making/build.md#chapters)) |

**Length.** A scene lasts as long as its **main box**'s frames, freezes included. The
main box is the box named `main`, or else the first shot or panel box. A scene without
one gives `seconds`, and a scene with one may not: its length is in its frames, so
giving it twice could only disagree.

## Audio

One track, or a list. Each has `file` (required), `offset` (seconds into the track to
start from, `0`), `start` (seconds into the film, `0`), `volume` (`1` as recorded),
`fade` (`[in, out]` seconds) and `licence` (a note kept with it). Music files stay out
of the repository.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `audio.file` | path | required | the sound file, from the film file's folder |
| `audio.offset` | seconds | `0` | where in the file to start playing |
| `audio.start` | seconds | `0` | when in the film the track starts |
| `audio.volume` | number | `1` | gain; `1` is as recorded |
| `audio.fade` | `[in, out]` seconds | `[0, 0]` | fade in from the track's start, fade out to its end |
| `audio.licence` | text | none | a note, not used |

The build measures every file's length rather than trusting a plan (the prototype's
planned and measured lengths differed by a second). A track plays until the picture
ends or the file runs out, whichever comes first, and its fade out ends there, so music
shorter than the film fades to silence instead of stopping. Tracks are added, not
averaged, so two tracks at `volume: 0.5` sound as one at `1`. Silence fills the rest of
the picture. An `offset` past the file's end, or a `start` after the picture's end, is
an error. `build(..., mute=True)` (`film build --mute`) leaves the sound out.

## The watermark

A signature, logo or watermark, at one of two levels. Its keys:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `watermark.image` | file | | a picture (PNG with transparency is best), kept **outside** the repository; it must exist |
| `watermark.text` | string | | a line of text in Lato; give `image` or `text` |
| `watermark.corner` | `upper_left`, `upper_right`, `lower_left`, `lower_right` | `lower_right` | 2% of the picture's height from the edges |
| `watermark.place` | `[x, y]` | | its upper left corner, instead of `corner` |
| `watermark.size` | number | `32` | pixels high: an image's height, or the text's font size (as a caption's `size`) |
| `watermark.opacity` | 0 to 1 | `0.7` | multiplies the image's own transparency |
| `watermark.colour` | colour | `'#f2f2f2'` | of text |
| `watermark.scenes` | list of scene names | | film level only: show it on these scenes |
| `watermark.shots` | list of names | | a film of shots only: show it on these shots |
| `watermark.seconds` | `[start, end]` | | film level only: show it between these film seconds |
| `watermark.cards` | bool | `false` | a film of shots only: show it on cards too |

**Film level** (`watermark:` in `film.yml`). It is drawn at the build, on each
scene's frames, so changing it never re-renders a shot. By default it shows on every
scene; `scenes:` or `seconds:` limit it.

**Shot level** (`watermark:` in a shot file), for frames used outside a film:

```yaml

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

## Examples

Each needs no data and writes into a folder you give it.

- `examples/film_timeline/run.py DIR`: a short film's plan (`film lengths`) and its
  captions' times (`film srt`), nothing drawn.
- `examples/film_build/run.py DIR` (needs ffmpeg): a title scene, a wake with a freeze and
  captions, its last frame held, a tone, chapters; `film.mp4`, a preview copy, `film.srt`,
  `chapters.txt` and `contact.png`. Run it twice: the second run keeps every clip.
- `examples/film_commands/run.sh DIR`: the same film through the `film` commands.
- `examples/film_project/run.py DIR` (needs ffmpeg): a film of the comparison example's two
  cases, wakes and live plots with a freeze, and a watermark.
