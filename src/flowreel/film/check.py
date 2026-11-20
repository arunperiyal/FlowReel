"""Checking a film without watching it (plan Section 10.8): subtitles and a contact sheet.

**Subtitles.** :func:`srt` writes the captions as a SubRip file, ``film.srt``, with
their film times from the timeline: for a player's subtitle track, a transcript, or
captions on a site that takes them. Mathematics between ``$`` is turned into plain
text (``$U_r = 5.4$`` becomes ``U_r = 5.4``, ``\\times`` becomes ``×``), since
subtitles have no maths font.

**Contact sheet.** :func:`contact` lays stills of the finished film on one picture,
``contact.png``, each labelled with its film time and shot, with the captions drawn in
place as they show. Stills are taken (:func:`contact_times`):

- ``caption``: at the middle of each caption, when it is fully faded in;
- ``freeze``: at the middle of each freeze;
- ``every:S``: every ``S`` seconds from the start.

The stills come from the finished clips, built when missing, so the sheet shows what
the film will show; no join is needed.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from flowreel.film.timeline import EPS

SYMBOLS = {"times": "×", "cdot": "·", "pm": "±", "approx": "≈", "sim": "~", "le": "≤",
           "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "infty": "∞", "partial": "∂",
           "nabla": "∇", "circ": "°", "degree": "°", "prime": "′", "to": "→",
           "rightarrow": "→", "ldots": "…", "dots": "…", "quad": " ", "qquad": " "}
WRAPPERS = ("mathrm", "mathbf", "mathit", "mathsf", "text", "textrm", "operatorname")


def plain(text: str) -> str:
    """``text`` with its ``$...$`` mathematics written as plain text (see the module)."""
    def maths(m: re.Match) -> str:
        s = m.group(1)
        s = re.sub(r"\\(?:%s)\s*\{([^{}]*)\}" % "|".join(WRAPPERS), r"\1", s)
        s = re.sub(r"\\[,;:! ]", " ", s)
        s = re.sub(r"\\([A-Za-z]+)", lambda c: command(c.group(1)), s)
        return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "")).strip()
    return re.sub(r"(?<!\\)\$(.*?)(?<!\\)\$", maths, text).replace(r"\$", "$")


def command(name: str) -> str:
    """A maths command's plain text: a symbol, a Greek letter (``alpha``: α,
    ``Delta``: Δ), or the name itself."""
    if name in SYMBOLS:
        return SYMBOLS[name]
    case = "CAPITAL" if name[0].isupper() else "SMALL"
    try:
        return unicodedata.lookup(f"GREEK {case} LETTER {name.upper()}")
    except KeyError:
        return name


def srt_time(seconds: float) -> str:
    """``seconds`` as SubRip's ``HH:MM:SS,mmm``."""
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_text(line) -> str:
    """The captions of the :class:`~flowreel.film.timeline.Timeline` ``line`` as a
    SubRip file's text, in order of their start."""
    blocks = []
    for k, c in enumerate(line.captions, start=1):
        words = "\n".join(plain(t) for t in c.caption.lines)
        blocks.append(f"{k}\n{srt_time(c.start)} --> {srt_time(c.end)}\n{words}\n")
    return "\n".join(blocks)


def srt_path(output: Path) -> Path:
    """Where the subtitles of the film ``output`` go: ``film.srt`` for ``film.mp4``."""
    return Path(output).with_suffix(".srt")


def srt(line, path: Path | None = None) -> Path:
    """Write the subtitles of ``line`` to ``path`` (default :func:`srt_path` of the
    film's output); returns the path."""
    path = Path(path) if path is not None else srt_path(line.film.output)
    path.write_text(srt_text(line), encoding="utf-8")
    return path


@dataclass(frozen=True)
class Still:
    """A still of the contact sheet: at ``time`` seconds of film, in shot ``shot``,
    ``why`` it was taken (a caption's first line, ``freeze``, or empty)."""

    time: float
    shot: str
    why: str = ""


def contact_times(line, at: str = "caption") -> list[Still]:
    """Where :func:`contact` takes stills (see the module): ``at`` is ``caption``,
    ``freeze`` or ``every:S``."""
    def shot_at(t: float) -> str:
        for ts in line.shots:
            if t < ts.end - EPS:
                return ts.shot.name
        return line.shots[-1].shot.name
    if at == "caption":
        out = [Still((c.start + c.end) / 2, "", plain(c.caption.lines[0])) for c in line.captions]
    elif at == "freeze":
        out = [Still(ts.start + tf.start + tf.hold / 2, ts.shot.name, "freeze")
               for ts in line.shots for tf in ts.freezes]
    elif at.startswith("every:"):
        try:
            step = float(at.split(":", 1)[1])
        except ValueError:
            step = 0.0
        if not step > 0:
            raise ValueError(f"contact: 'every:S' needs a number of seconds above 0, got {at!r}")
        out = [Still(k * step, "") for k in range(math.ceil(line.length / step - EPS))]
    else:
        raise ValueError(f"contact: at is 'caption', 'freeze' or 'every:S', got {at!r}")
    return [Still(s.time, s.shot or shot_at(s.time), s.why) for s in out]


def contact_path(output: Path) -> Path:
    """Where the contact sheet of the film ``output`` goes: ``contact.png`` beside it."""
    return Path(output).with_name("contact.png")


def grab(clip: Path, frame: int, size: tuple[int, int]):
    """Frame ``frame`` (from 0) of ``clip``, decoded, as a Pillow image of ``size``."""
    import subprocess

    from PIL import Image

    from flowreel.film import ffmpeg as ff
    w, h = size
    done = subprocess.run(
        [str(ff.find().ffmpeg), "-v", "error", "-i", str(clip), "-vf",
         f"select=eq(n\\,{frame}),scale={w}:{h}:in_color_matrix=bt709:in_range=tv",
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if done.returncode != 0 or len(done.stdout) != w * h * 3:
        raise ff.FfmpegError(f"cannot read frame {frame} of {clip}: {done.stderr[-1000:]!r}")
    return Image.frombytes("RGB", (w, h), done.stdout)


def contact(film, at: str = "caption", path: Path | None = None, *, columns: int = 4,
            width: int = 480, folder=None, force: bool = False,
            panels: dict | None = None) -> Path:
    """Draw the contact sheet of ``film`` (a :class:`~flowreel.film.Film` or a film
    file's path) with stills ``at`` (see :func:`contact_times`), ``columns`` across,
    each ``width`` pixels wide (at most the film's), into ``path`` (default
    :func:`contact_path`). ``folder``, ``force`` and ``panels`` are as for
    :func:`~flowreel.film.build.build`. Returns the path."""
    from PIL import Image, ImageDraw

    from flowreel.film.build import _film
    from flowreel.film.cards import font
    from flowreel.film.clips import Clips
    film = _film(film)
    clips = Clips(film, folder=folder, force=force, panels=dict(panels or {}))
    stills = contact_times(clips.line, at)
    if not stills:
        raise ValueError(f"contact: the film has no {at.split(':')[0]}s to take stills at")
    fw, fh = film.size
    w = min(width, fw)
    w -= w % 2
    h = round(fh * w / fw)
    label, gap = max(14, round(w / 28)), max(4, round(w / 60))
    fnt = font("regular", label)
    cols = max(1, min(columns, len(stills)))
    rows = math.ceil(len(stills) / cols)
    cell = h + label * 2 + gap
    sheet = Image.new("RGB", (gap + cols * (w + gap), gap + rows * cell), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for k, s in enumerate(stills):
        ts = clips.line.shot(s.shot)
        frames = round(ts.length * film.fps)
        frame = min(int((s.time - ts.start) * film.fps + EPS), frames - 1)
        image = grab(clips.finished(s.shot).path, frame, (w, h))
        x = gap + (k % cols) * (w + gap)
        y = gap + (k // cols) * cell
        sheet.paste(image, (x, y))
        text = f"{s.time:.2f} s  {s.shot}" + (f"  {s.why}" if s.why else "")
        while draw.textlength(text, font=fnt) > w and len(text) > 4:
            text = text[:-2] + "…"
        draw.text((x, y + h + label * 0.4), text, font=fnt, fill=(220, 220, 220))
    path = Path(path) if path is not None else contact_path(film.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path
