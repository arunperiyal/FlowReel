# Layouts and boxes

A scene shows its **layout**: a background and boxes, drawn in order, the first at the
back. Each box shows one thing, its kind ([boxes](boxes.md)); this page is where and
when a box shows, how a frame is drawn, and the window that designs a layout.

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

The point is projected on each frame by the camera that drew it. A text box's upper left corner goes on the point,
an arrow's tip, and a rectangle's or circle's centre.


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

## Designing a layout: `scene design`

```text
flowreel scene design compare
```

A window on one scene's layout, drawn as the build draws it at the *Time* slider's
moment: shots' frames, panels, pictures and text, with each box's outline and name over
them.

- **Drag on empty space** to draw a box (a text box, to fill); **drag a box** to move it;
  **drag a corner** of the selected box to resize it. Edges, and a box's centre, snap
  to other boxes' edges and centres and to the frame's within 8 pixels, else to the grid
  (`--grid`, 20 pixels; `g` turns it off).
- **Name and fill** the selected box in the panel on the right: its kind, and a line of
  content (a text's lines with `|` between them; a file for an image, shot or panel; a
  shape's kind; a scene's name for `last_frame`), then *Apply*.
- **Keys:** `u` undo, `delete` remove the selected box, `t` the next second.

Every change is checked as the film would read it and written at once: to the layout's
file, or for a layout written in the scene, to that scene's `layout:` block of
`film.yml`, the rest of the file, comments and all, as it was. A change that would not
read is not made, and the status line says why. A box moved or resized is written with
`pos` and `size` (a `place` becomes them); a box that follows a point of the flow is
placed by the flow, so it is not moved by hand.

## Errors

The file is checked when it is read, and an error names the file and the key: the
layout file's own name for a box written there (`layouts/compare.yml: boxes[2].text:
missing key 'lines'`). Among the checks: a box shows one kind; a name is not used twice;
`follow` names a shot box; `at` lies inside a scene of known `seconds`; a scene has
`seconds` exactly when it has no main box; `last_frame` names another scene.

## Examples

- `examples/scene_layouts/run.py DIR`: frame folders in boxes, side by side and on a grid,
  with text labels; `film lengths` and `scene preview`.
- `examples/compare/run.py DIR`: the comparison of two generated cases (wakes and live
  plots, a freeze) and a lift map, as two scenes.
- `examples/flow_panels/run.py` and `examples/panels/run.py`: panels tiled in a scene.
