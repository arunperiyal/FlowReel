"""A commented film file with the defaults, for ``flowreel film template``.

Every key of the film file (plan Section 10.1) is written at its default, taken from the
schema's own dataclasses (:class:`~flowreel.film.schema.FilmStyle`, ``CaptionStyle``,
``Audio``, ``Watermark``), each with a comment. Keys with no default, and the kinds of
shot that need a file, are written commented out. The result loads as a film once its
frames folder holds frames.
"""
from __future__ import annotations

import yaml

from flowreel.film.schema import (ALIGN, CORNERS, DEFAULT_SIZE, MATHS, TO_OUTPUT, Audio,
                                  CaptionStyle, FilmStyle, Watermark)

COLUMN = 40


def _v(value) -> str:
    """``value`` as YAML in one line."""
    if isinstance(value, tuple):
        value = list(value)
    text = yaml.safe_dump(value, default_flow_style=True, width=1000).strip()
    return text.removesuffix("...").strip()


def _line(text: str, comment: str = "") -> str:
    return f"{text.ljust(COLUMN)}# {comment}" if comment else text


def template(name: str = "my_shot", fps: int = 24) -> str:
    """The text of a film file whose one frames shot is ``name`` (frames in
    ``frames/<name>``), at ``fps`` frames a second."""
    st, cap, a, w = FilmStyle(), CaptionStyle(), Audio(file=None), Watermark()
    lines = [
        "# Film file written by `flowreel film template`. Reference: docs/film.md; captions",
        "# and shapes: docs/captions.md; cards: docs/cards.md; the build: docs/build.md.",
        _line("output: film.mp4", "the film, from this file's folder"),
        _line(f"fps: {fps}", "frames a second of the film"),
        _line(f"size: {_v(DEFAULT_SIZE)}", "width, height in pixels"),
        "style:",
        _line(f"  font: {st.font}", "font family of the text; Lato is bundled"),
        _line(f"  maths: {st.maths}", "text between $: font (the text's own) or one of "
              + ", ".join(m for m in MATHS if m != "font")),
        "  colours:",
        _line(f"    text: {_v(st.text)}", "captions, unless a caption says"),
        _line(f"    muted: {_v(st.muted)}", "small print on cards"),
        "  caption:                              # every caption's look, unless it says",
        _line(f"    size: {_v(cap.size)}", "letter size, pixels"),
        _line(f"    shadow: {_v(cap.shadow)}", "a soft shadow behind the text"),
        _line(f"    box: {_v(cap.box)}", "a dark box behind the text"),
        _line(f"    fade: {_v(cap.fade)}", "fade in and out, seconds"),
        _line(f"    margin: {_v(cap.margin)}", "from the edge for top and bottom, pixels"),
        _line(f"    align: {cap.align}", "one of " + ", ".join(ALIGN)),
        _line(f"    spacing: {_v(cap.spacing)}", "line spacing, times the size"),
        "# audio:                                # one or more tracks; lengths measured from the files",
        f"#   - {{file: assets/music.mp3, offset: {_v(a.offset)}, start: {_v(a.start)}, "
        f"volume: {_v(a.volume)}, fade: {_v(a.fade)}, licence: ~}}",
        "# watermark:                            # an image or a line of text, drawn at the build",
        f"#   {{text: 'A. Periyal', corner: {w.corner}, size: {_v(w.size)}, "
        f"opacity: {_v(w.opacity)}, colour: {_v(w.colour)}, cards: {_v(w.cards)}}}",
        f"#   # or image: FILE in place of text; place: [x, y] in place of corner "
        f"({', '.join(CORNERS)});",
        "#   # shots: [NAME, ...] or seconds: [start, end] to show it only there",
        "shots:                                  # in order; each one of frames, layout, card, hold_last_of",
        "  # - {name: opening, card: cards/opening.yml, seconds: 5, fade: [1.5, 1.5], chapter: Opening}",
        _line(f"  - name: {name}", "unique; captions and holds refer to it"),
        _line(f"    frames: frames/{name}", "a folder of frame_00000.png ...; or layout: FILE"),
        _line(f"    rate: {{fps: {fps}, to_output: interpolate}}",
              "frames a second of the shot, made up by " + ", ".join(TO_OUTPUT)),
        _line("    freezes: []", "[{at: S, hold: S, text: ...}], at in the shot's frames"),
        _line("    fade: [0.0, 0.0]", "in, out, seconds"),
        _line("    # fade_out_at: ~", "seconds into the shot the fade out starts"),
        _line("    text: []", "captions, or a text file such as text/my_shot.yml"),
        _line("    # chapter: ~", "a title, or {title: T, at: S}, starts a chapter"),
        f"  # - {{name: end, hold_last_of: {name}, seconds: 5, overlays: true, fade: [0, 2]}}",
    ]
    return "\n".join(lines) + "\n"
