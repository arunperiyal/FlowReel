# A film of scenes

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

`flowreel film template --scenes` writes a film of scenes with every key, and `--layout`
a layout file. `film build`, `check`, `lengths`, `srt` and `chapters` read a film of
scenes as they read a film of shots ([building it](#building-it)).

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

## The film

| Key | Type | Default | Meaning |
|---|---|---|---|
| `output` | path | `film.mp4` | the film, from the film file's folder |
| `fps` | integer | `24` | frames a second of the film |
| `size` | `[width, height]` | `[1920, 1080]` | the film's pixels; boxes are placed in them |
| `style` | mapping | the defaults below | fonts, colours and the looks of text |
| `audio` | list | none | tracks, as [the film file](film.md) gives them |
| `watermark` | mapping | none | as [the watermark](captions.md#the-watermark) gives it, with `scenes` in place of `shots` |
| `watermark.scenes` | list of scene names | every scene | the scenes it shows on (or `seconds: [start, end]`) |
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
| `scenes.chapter` | title, or `{title, at}` | none | starts a chapter, as [chapters](build.md) say |

**Length.** A scene lasts as long as its **main box**'s frames, freezes included. The
main box is the box named `main`, or else the first shot or panel box. A scene without
one gives `seconds`, and a scene with one may not: its length is in its frames, so
giving it twice could only disagree.

## Layouts

A layout is written under its scene, or in its own file, `layouts/NAME.yml`, named by
`layout: NAME`. A layout in a file can serve several scenes, and paths in it are taken
from the file's own folder (`../shots/wake.yml`), as every path in FlowReel is
([rules](../projects/rules.md)).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `background` | colour | `black` | behind the boxes |
| `boxes` | list | required | drawn in order, the first at the back |

## Boxes

A box's own keys say where and when it shows. What it shows is under one key, its kind,
written short (`text: 'Hello'`) or as a mapping of the kind's options.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `boxes.name` | string | the kind and its number (`text2`) | unique in the layout; `follow` and `main` name it |
| `boxes.pos` | `[x, y]` | none | the upper left corner, pixels of the film, `y` down |
| `boxes.size` | `[w, h]` | none | width and height in pixels; a shot is drawn at this size |
| `boxes.place` | `full`, `top`, `bottom`, `left`, `right`, `centre`, `top_left`, `top_right`, `bottom_left`, `bottom_right` | `full` | a half, the middle half, or a quarter of the frame, instead of `pos` and `size` |
| `boxes.at` | `[start, end]` | the whole scene | seconds into the scene; `end` `~` runs to the scene's end |
| `boxes.fade` | seconds, or `[in, out]` | a text's look; else `0` | fading in and out at `at`'s ends |
| `boxes.follow` | `{box, model, offset}` | none | for text and shapes: pinned to a point of the flow in a shot box |
| `boxes.text`, `.image`, `.shape`, `.shot`, `.panel`, `.last_frame` | below | one is required | what the box shows |

A box with neither `pos` nor `place` fills the frame. A text box may give `pos` alone and
is then as large as its text. A box of another kind at `pos` needs its `size`.

### `follow`: a box on a point of the flow

| Key | Type | Default | Meaning |
|---|---|---|---|
| `follow.box` | a shot box's name | required | the shot whose camera places the point |
| `follow.model` | `[x, y, z]` | required | the point, in the flow's units |
| `follow.offset` | `[dx, dy]` | `[0, 0]` | pixels moved on the screen after projection |

The point is projected on each frame by the camera that drew it, as
[anchored captions](captions.md) are. A text box's upper left corner goes on the point,
an arrow's tip, and a rectangle's or circle's centre.

### `text`

Short: a line, or a list of lines. `$...$` is mathematics.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `text.lines` | a line or a list | required | the text |
| `text.look` | `title`, `text`, `small` | `text` | the look it starts from |
| `text.size`, `.colour`, `.weight`, `.align`, `.valign`, `.spacing`, `.shadow`, `.box`, `.fade`, `.margin` | as a look's | the look's | change the look for this box |
| `text.subtitle` | true or false | `true` | a timed text box (one with `at`) is a subtitle in `film.srt` |

### `image`

Short: the picture's file.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `image.file` | path | required | the picture; keep logos in `assets/`, outside FlowReel |
| `image.fit` | `contain`, `cover`, `stretch` | `contain` | all of it in the box; the box filled, cut to fit; or stretched |
| `image.opacity` | 0 to 1 | `1` | |

### `shape`

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

### `shot`

Short: the shot file. Its frames are the shot's, under `frames/<its name>`. Shots are
rendered beforehand (`shot render`, or on Slurm).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `shot.file` | path | required (or `frames`) | the shot file |
| `shot.frames` | folder | none | frames drawn elsewhere, instead of a shot file |
| `shot.rate` | `{fps, to_output}` | the film's rate | as a [shot of a film](film.md#shots) has it |
| `shot.freezes` | list of `{at, hold}` | none | stop at `at` seconds of the shot's frames for `hold` seconds; the other boxes go on |
| `freezes.at` | seconds | required | when, in seconds of the shot's own frames |
| `freezes.hold` | seconds > 0 | required | how long the frame is held |

### `panel` and `last_frame`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `panel.file` | path | required | a panel file; the build draws it at the box's size, at the film's rate |
| `panel.rate` | `{fps}` | the film's rate | its frames a second (its `times` in order); the build draws every output frame at the time between two frames, so a panel is never interpolated |
| `panel.freezes` | list of `{at, hold}` | none | as a shot's |
| `last_frame` | a scene's name | required | that scene's last frame, held (give the scene `seconds`) |

## How a frame is drawn

A scene's frame at a time is its layout's background, then each box that shows at that
time, the first at the back. A box with `at` fades in over its fade's first number and
out over its second, and a text box with `at` and no `fade` takes its look's. A box
without `at` shows for the whole scene and does not fade: the scene's own `fade` and
`cross` take it in and out.

Text is set as captions are, in the film's font with `$...$` as mathematics, and given
a soft shadow or a dark box. A text box at `pos` in the `text` look draws the same
pixels as a caption placed there, so captions move to text boxes unchanged. A shot's,
panel's or held frame is fitted to its box, its aspect kept, and centred. A box that
follows a point is left out of a frame where the point is behind the camera or off the
picture.

## Building it

`flowreel film build` makes a clip per scene, then the film.

- **Length.** A scene of `seconds` lasts that long; otherwise its main box's frames at
  its `rate`, each shown for a whole step, plus its freezes. A shot box's frames are
  rendered beforehand. A missing one stops the build, naming the shot and the command
  that renders it. Every shot or panel box plays from the scene's start and holds its
  last frame once it ends.
- **Rates.** A shot at the film's rate, or under `to_output: repeat`, shows each frame
  as it is; `blend` cross-fades the two frames around a moment; `interpolate` makes the
  frames between with ffmpeg's motion interpolation, once, kept under `clips/`. A panel is
  drawn at the box's size on every output frame, at the time between two of its frames,
  so its dot moves smoothly and is never smeared.
- **A clip per scene,** each frame drawn as [above](#how-a-frame-is-drawn), faded from
  and to black by the scene's `fade`, with the watermark where it shows. The clip's name
  holds a key of everything in it, so a changed caption rebuilds one scene and keeps the
  others. A scene that holds another's last frame is rebuilt only when that frame's
  pixels change.
- **The film.** A scene's `cross` dissolves its last seconds into the next scene's
  first, so the film is the scenes' lengths less the crosses. Without a cross the clips
  are joined without encoding again. Audio, the preview copy (`--preview`) and
  `--only SCENE` work as for a [film of shots](build.md).
- **Subtitles and chapters.** Every text box with `at` (and `subtitle` left true) is a
  subtitle in `film.srt`, from the scene's start. A scene's `chapter` starts a chapter
  at the scene's start plus its `at`. `film lengths` prints each scene's planned length
  and, when its clip is built and current, its measured one; `film check` makes the
  contact sheet, with stills at the middle of each timed text box (`--at caption`), of
  each freeze (`--at freeze`) or every few seconds (`--at every:S`).

## Errors

The file is checked when it is read, and an error names the file and the key: the
layout file's own name for a box written there (`layouts/compare.yml: boxes[2].text:
missing key 'lines'`). Among the checks: a box shows one kind; a name is not used twice;
`follow` names a shot box; `at` lies inside a scene of known `seconds`; a scene has
`seconds` exactly when it has no main box; `last_frame` names another scene.
