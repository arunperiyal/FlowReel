"""Commented templates of a film of scenes and of a layout file (plan Section 19.11;
``flowreel film template --scenes`` and ``--layout``).

Every key is written at its default (taken from :mod:`flowreel.film.model`'s own
dataclasses) or as an example, each with a comment. The film template loads once its
shot file exists; the layout template loads as it is.
"""
from __future__ import annotations

from flowreel.film.model import (DEFAULT_LOOKS, DIRECTIONS, FITS, KINDS, LOOKS, PLACES,
                                 SHAPES, Look, Style)
from flowreel.film.schema import CORNERS, DEFAULT_SIZE, MATHS, TO_OUTPUT, Audio, Watermark
from flowreel.film.template import _line, _v

REFERENCE = "docs/guide/film/film.md"


def _look_line(name: str, look: Look) -> str:
    colour = "~" if look.colour is None else look.colour
    return (f"    {name}: {{size: {_v(look.size)}, colour: {colour}, weight: {look.weight}, "
            f"align: {look.align}, valign: {look.valign}, spacing: {_v(look.spacing)}, "
            f"shadow: {_v(look.shadow)}, box: {_v(look.box)}, fade: {_v(look.fade)}, "
            f"margin: {_v(look.margin)}}}")


def film_template(name: str = "my_shot", fps: int = 24) -> str:
    """The text of a film of scenes: a title scene, a scene of the shot ``name``
    (``shots/<name>.yml``) and an end scene holding its last frame, at ``fps``."""
    st, a, w = Style(), Audio(file=None), Watermark()
    lines = [
        "# A film of scenes, written by `flowreel film template --scenes`. Reference:",
        f"# {REFERENCE}. Levels: the film's properties, audio, watermark, then its scenes;",
        "# a scene has a layout of boxes (text, image, shape, shot, panel, last_frame).",
        _line("output: film.mp4", "the film, from this file's folder"),
        _line(f"fps: {fps}", "frames a second of the film"),
        _line(f"size: {_v(DEFAULT_SIZE)}", "width, height in pixels; boxes are placed in these"),
        "style:",
        _line(f"  font: {st.font}", "font family of the text; Lato is bundled"),
        _line(f"  maths: {st.maths}", "text between $: font (the text's own) or one of "
              + ", ".join(m for m in MATHS if m != "font")),
        "  colours:",
        _line(f"    text: {_v(st.text)}", "text and shapes, unless a box says"),
        _line(f"    muted: {_v(st.muted)}", "the small look, and colour: muted"),
        _line("  looks:", "how text looks, by name: " + ", ".join(LOOKS)
              + "; a text box starts from one"),
        *(_look_line(n, DEFAULT_LOOKS[n]) for n in LOOKS),
        "# audio:                                # one or more tracks; lengths measured from the files",
        f"#   - {{file: assets/music.mp3, offset: {_v(a.offset)}, start: {_v(a.start)}, "
        f"volume: {_v(a.volume)}, fade: {_v(a.fade)}, licence: ~}}",
        "# watermark:                            # an image or a line of text, on every frame",
        f"#   {{text: 'A. Author', corner: {w.corner}, size: {_v(w.size)}, "
        f"opacity: {_v(w.opacity)}, colour: {_v(w.colour)}}}",
        f"#   # or image: FILE in place of text; place: [x, y] in place of corner "
        f"({', '.join(CORNERS)});",
        "#   # scenes: [NAME, ...] or seconds: [start, end] to show it only there",
        "scenes:                                 # in order",
        _line("  - name: opening", "unique; last_frame and the watermark name it"),
        _line("    seconds: 5", "a scene of text and pictures says how long it is"),
        _line("    fade: [1.5, 1.5]", "from and to black: in, out, seconds"),
        _line("    chapter: Opening", "a title, or {title: T, at: S}, starts a chapter"),
        _line("    layout:", "in place, or the name of layouts/NAME.yml"),
        _line("      background: black", "behind the boxes"),
        _line("      boxes:", "drawn in order, the first at the back"),
        _line("        - name: title", "a box's name; default its kind and number"),
        _line("          text: {lines: ['My film', 'A subtitle'], look: title}",
              "a line, lines, or {lines, look, ...}"),
        _line("          place: centre", "one of " + ", ".join(PLACES)
              + "; or pos and size; or neither: the whole frame"),
        _line("        - {shape: line, pos: [760, 700], size: [400, 3]}",
              "a divider: a line across its box"),
        _line(f"  - name: {name}", "a scene of one shot box"),
        _line("    layout:", ""),
        "      boxes:",
        _line(f"        - shot: {{file: shots/{name}.yml, rate: {{fps: {fps}, to_output: interpolate}}, "
              "freezes: []}",
              "frames/<shot's name>; made up by " + ", ".join(TO_OUTPUT)),
        _line("        - text: ['Its caption']", "a caption, timed in the scene"),
        _line("          place: bottom", ""),
        _line("          at: [0.5, ~]", "seconds into the scene: [start, end]; ~ to its end"),
        _line("          fade: 0.8", "in and out, seconds; or [in, out]"),
        _line("    cross: 1.0", "seconds dissolving into the next scene (or fade: [in, out])"),
        _line("  - name: end", "holds the last frame of the shot's scene"),
        _line("    seconds: 4", ""),
        _line("    fade: [0, 2]", ""),
        f"    layout: {{boxes: [{{last_frame: {name}}}]}}",
    ]
    return "\n".join(lines) + "\n"


def layout_template() -> str:
    """The text of a layout file (``layouts/NAME.yml``) with one box of each kind,
    every key written or commented."""
    t = DEFAULT_LOOKS["text"]
    lines = [
        "# A layout, written by `flowreel film template --layout`: a scene's boxes. A film's",
        f"# scene names it as layout: NAME (this file is layouts/NAME.yml). Reference: {REFERENCE}.",
        "# Boxes are drawn in order, the first at the back. Each has a place and a time, and",
        "# one of: " + ", ".join(KINDS) + ". Paths are from this file's folder (layouts/), so",
        "# a shot of shots/ is ../shots/NAME.yml.",
        _line("background: black", "behind the boxes"),
        "boxes:",
        _line("  - name: main", "the main box: its frames set the scene's length"),
        _line("    shot: ../shots/wake.yml", "a shot file; or {file, rate, freezes}, or {frames: DIR}"),
        _line("    pos: [0, 0]", "upper left corner, pixels of the film"),
        _line("    size: [1280, 1080]", "width, height; the shot is drawn at this size"),
        _line("  - name: lift", ""),
        _line("    panel: ../panels/lift.yml", "a panel, drawn by the build at the box's size"),
        _line("    place: right", "one of " + ", ".join(PLACES)),
        _line("  - name: label", ""),
        "    text:",
        _line("      lines: ['Wake', '$Re = 1000$']", "$...$ is mathematics"),
        _line("      look: text", "one of " + ", ".join(LOOKS) + "; the keys below change it"),
        _line(f"      size: {_v(t.size)}", "letter size, pixels"),
        _line("      colour: ~", "~: the film's text colour; or muted, or a colour"),
        _line(f"      weight: {t.weight}", "regular, light, bold or italic"),
        _line(f"      align: {t.align}", "the lines: centre, left or right"),
        _line(f"      valign: {t.valign}", "in the box: top, centre or bottom"),
        _line(f"      spacing: {_v(t.spacing)}", "line spacing, times the size"),
        _line(f"      shadow: {_v(t.shadow)}", "a soft shadow behind the text"),
        _line(f"      box: {_v(t.box)}", "a dark box behind the text"),
        _line(f"      margin: {_v(t.margin)}", "from the box's edges, pixels"),
        _line("      subtitle: true", "a timed text box goes into film.srt"),
        _line("    follow: {box: main, model: [6, 0.42, 0.18], offset: [40, -120]}",
              "pinned to a point of the flow in box main"),
        _line("    at: [1.0, 6.0]", "seconds into the scene; end ~: to the scene's end"),
        _line(f"    fade: {_v(t.fade)}", "in and out; or [in, out]"),
        _line("  - name: pointer", ""),
        _line("    shape: {kind: arrow, colour: ~, width: 4, head: 18, direction: down_left, shadow: true}",
              "kinds " + ", ".join(SHAPES) + "; directions " + ", ".join(DIRECTIONS)),
        _line("    follow: {box: main, model: [6, 0.42, 0.18]}", "the arrow's tip on the point"),
        _line("    size: [120, 90]", ""),
        _line("    at: [1.0, 6.0]", ""),
        _line("  # - {image: {file: ../assets/logo.png, fit: contain, opacity: 1.0}, place: top_left}",
              "fit: " + ", ".join(FITS)),
        _line("  # - {shape: {kind: rectangle, fill: '#00000080', radius: 8}, pos: [40, 40], size: [500, 200]}", ""),
        _line("  # - {last_frame: SCENE}", "another scene's last frame, held"),
    ]
    return "\n".join(lines) + "\n"
