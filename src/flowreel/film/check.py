"""Checking a film without watching it (plan Section 10.8): the pieces of its subtitles
and contact sheet.

Mathematics between ``$`` is turned into plain text (:func:`plain`: ``$U_r = 5.4$``
becomes ``U_r = 5.4``, ``\\times`` becomes ``×``), since subtitles have no maths font.
:func:`srt_time` and :func:`srt_path` write SubRip's times and name its file;
:func:`grab` reads a frame of a clip and :func:`font` is the label font, for the contact
sheet. :mod:`flowreel.film.scene_build` writes both the subtitles and the sheet.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

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


def srt_path(output: Path) -> Path:
    """Where the subtitles of the film ``output`` go: ``film.srt`` for ``film.mp4``."""
    return Path(output).with_suffix(".srt")


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


def font(weight: str, size: float, family: str = "Lato"):
    """A font of ``family`` and ``weight`` (``regular``, ``light``, ``bold`` or
    ``italic``) at ``size`` pixels, for Pillow. Lato is the bundled copy; another family
    is found among the machine's fonts through matplotlib, at the nearest weight (Times
    New Roman has no light weight, so its regular is used). A family that is not
    installed is an error naming it. Text is kerned where Pillow can
    (:func:`~flowreel.scene.text.pillow_font`)."""
    from flowreel.scene.text import font_file, pillow_font
    if family == "Lato":
        return pillow_font(font_file(weight.capitalize()), round(size))
    from matplotlib import font_manager
    props = font_manager.FontProperties(
        family=family, style="italic" if weight == "italic" else "normal",
        weight={"italic": "normal", "regular": "normal"}.get(weight, weight))
    try:
        path = font_manager.findfont(props, fallback_to_default=False)
    except ValueError:
        raise ValueError(f"font {family!r} is not installed on this machine (style: font in "
                         "the film file)") from None
    return pillow_font(path, round(size))
