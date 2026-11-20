"""Chapters written out (plan Section 10.9): in the film's file, and for YouTube.

The timeline places each chapter (:class:`~flowreel.film.timeline.TimedChapter`). The
build gives them to ffmpeg at the join as a metadata file (:func:`metadata_text`:
``;FFMETADATA1``, one ``[CHAPTER]`` each, in milliseconds) with ``-map_chapters``, so
nothing is re-encoded; the preview copy keeps them. Desktop players (VLC, mpv, IINA,
QuickTime) show them as a chapter menu.

YouTube ignores chapters in the file and reads timestamps from a video's description
instead, so the build also writes ``chapters.txt`` (:func:`youtube_text`): one line per
chapter, ``0:00 Opening``. YouTube shows chapters only when the first is at ``0:00``,
there are at least three, and each lasts at least ten seconds; :func:`youtube_notes`
says which of these a film misses, as notes, not errors (a talk's file may never go
there).
"""
from __future__ import annotations

import math
from pathlib import Path

YOUTUBE_MIN_CHAPTERS = 3
YOUTUBE_MIN_SECONDS = 10.0


def _escape(text: str) -> str:
    """``text`` escaped for an ffmpeg metadata file (``=``, ``;``, ``#``, ``\\``)."""
    for c in "\\=;#":
        text = text.replace(c, "\\" + c)
    return text


def metadata_text(chapters, length: float | None = None) -> str:
    """The ffmpeg metadata file of ``chapters`` (``TimedChapter``), times in
    milliseconds. ``length`` (seconds), when given, ends the last chapter instead of
    its planned end (the measured film may differ by a frame's rounding)."""
    out = [";FFMETADATA1"]
    for k, c in enumerate(chapters):
        end = length if length is not None and k == len(chapters) - 1 else c.end
        out += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(c.start * 1000)}",
                f"END={round(end * 1000)}", f"title={_escape(c.title)}"]
    return "\n".join(out) + "\n"


def timestamp(seconds: float) -> str:
    """``seconds`` as YouTube writes a time: ``0:07``, ``12:34``, ``1:02:03``. Whole
    seconds, rounded down, so a chapter never starts late."""
    s = math.floor(seconds + 1e-6)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def youtube_text(chapters) -> str:
    """``chapters`` as ``chapters.txt``: ``0:00 Opening``, one per line."""
    return "".join(f"{timestamp(c.start)} {c.title}\n" for c in chapters)


def youtube_notes(chapters) -> list[str]:
    """What YouTube needs that ``chapters`` miss (see the module); empty when none."""
    if not chapters:
        return []
    notes = []
    if timestamp(chapters[0].start) != "0:00":
        notes.append(f"chapters: the first starts at {timestamp(chapters[0].start)}; YouTube "
                     "needs one at 0:00")
    if len(chapters) < YOUTUBE_MIN_CHAPTERS:
        notes.append(f"chapters: {len(chapters)} of them; YouTube needs at least "
                     f"{YOUTUBE_MIN_CHAPTERS}")
    short = [c.title for c in chapters if c.end - c.start < YOUTUBE_MIN_SECONDS]
    if short:
        notes.append(f"chapters shorter than YouTube's {YOUTUBE_MIN_SECONDS:g} s: "
                     + ", ".join(short))
    return notes


def chapters_path(output: Path) -> Path:
    """Where the YouTube timestamps of the film ``output`` go: ``chapters.txt`` beside
    it."""
    return Path(output).with_name("chapters.txt")
