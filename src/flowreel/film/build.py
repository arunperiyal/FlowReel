"""The film build (plan Section 10.8): finished clips joined into ``film.mp4``.

:func:`build` makes every shot's finished clip (:class:`~flowreel.film.clips.Clips`,
each kept by its key) and joins them in order with ffmpeg's ``concat`` demuxer, copying
the picture: every clip is encoded alike, so nothing is encoded again and a join of an
hour's film takes seconds.

**Lengths.** Each shot's planned length comes from the timeline, its measured length
from its clip (``ffprobe``); the report prints both, so a clip that came out short is
seen at once. The film's measured length is the sum of its clips'.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.film import ffmpeg as ff


@dataclass(frozen=True)
class ShotLength:
    """One shot of a build: its ``name``, ``planned`` and ``measured`` seconds, and
    whether its finished clip was ``built`` now (``False``: kept)."""

    name: str
    planned: float
    measured: float
    built: bool


@dataclass
class Built:
    """What a build wrote: the ``output`` film, the ``shots`` with their lengths, the
    film's ``planned`` and ``measured`` seconds."""

    output: Path
    shots: list[ShotLength]
    planned: float
    measured: float
    notes: list[str] = field(default_factory=list)

    def table(self) -> list[str]:
        """The report as lines: one per shot (planned, measured, built or kept), then
        the film, then any notes."""
        width = max([len(s.name) for s in self.shots] + [4])
        out = [f"{'shot':{width}s}  planned  measured"]
        for s in self.shots:
            out.append(f"{s.name:{width}s}  {s.planned:6.2f} s  {s.measured:6.2f} s  "
                       f"{'built' if s.built else 'kept'}")
        out.append(f"{'film':{width}s}  {self.planned:6.2f} s  {self.measured:6.2f} s  "
                   f"{self.output}")
        return out + self.notes


def _film(film):
    from flowreel.film.schema import Film, load
    return film if isinstance(film, Film) else load(film)


def concat_list(paths, listing: Path) -> Path:
    """Write the ``concat`` demuxer's list of ``paths`` (absolute, quoted) to
    ``listing``."""
    def quote(p: Path) -> str:
        return "'" + str(Path(p).resolve()).replace("'", "'\\''") + "'"
    listing.write_text("".join(f"file {quote(p)}\n" for p in paths))
    return listing


def build(film, *, folder=None, force: bool = False, panels: dict | None = None) -> Built:
    """Build ``film`` (a :class:`~flowreel.film.Film` or a film file's path) into its
    ``output``.

    ``folder`` keeps the clips (default ``clips/`` beside the film file); ``force``
    rebuilds every clip; ``panels`` are options for drawing a layout's ``rate: output``
    panels (such as ``jobs``). Returns a :class:`Built`."""
    from flowreel.film.clips import Clips
    film = _film(film)
    clips = Clips(film, folder=folder, force=force, panels=dict(panels or {}))
    finished, shots = [], []
    for ts in clips.line.shots:
        clip = clips.finished(ts.shot.name)
        finished.append(clip)
        shots.append(ShotLength(ts.shot.name, ts.length, ff.length(clip.path), clip.built))
    measured = sum(s.measured for s in shots)
    out = Path(film.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = concat_list([c.path for c in finished], clips.folder / "film_list.txt")
    tmp = out.with_name(out.stem + ".part" + out.suffix)
    ff.run("-f", "concat", "-safe", 0, "-i", listing, "-map", "0:v", "-c", "copy",
           "-movflags", "+faststart", tmp)
    os.replace(tmp, out)
    return Built(out, shots, clips.line.length, measured)
