"""The film build (plan Section 10.8): finished clips joined into ``film.mp4``.

:func:`build` makes every shot's finished clip (:class:`~flowreel.film.clips.Clips`,
each kept by its key) and joins them in order with ffmpeg's ``concat`` demuxer, copying
the picture: every clip is encoded alike, so nothing is encoded again and a join of an
hour's film takes seconds.

**Lengths.** Each shot's planned length comes from the timeline, its measured length
from its clip (``ffprobe``); the report prints both, so a clip that came out short is
seen at once. The film's measured length is the sum of its clips'.

**Audio** (plan Section 10.6). Each track of ``audio`` is read from ``offset`` seconds
into its file, at ``volume``, and starts ``start`` seconds into the film; tracks are
mixed (added, not averaged) and the whole cut to the picture. Lengths are measured from
the files, not planned (the prototype's planned and measured lengths differed by a
second): a track plays until the picture or the file ends, whichever comes first, and
its fade out ends there. Silence fills the rest, so the sound runs as long as the
picture. ``mute`` builds the film without sound. Sound is encoded as AAC at 192 kb/s;
the picture is still copied.
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


@dataclass(frozen=True)
class TrackPlan:
    """A track placed: its ``audio`` settings, ``length`` of its file in seconds
    (measured), and the film seconds it plays, ``start`` to ``end``."""

    audio: object
    length: float
    start: float
    end: float


def plan_tracks(tracks, picture: float, lengths: dict | None = None) -> list[TrackPlan]:
    """Place ``tracks`` (:class:`~flowreel.film.schema.Audio`) under a picture of
    ``picture`` seconds. ``lengths`` gives a file's length; others are measured. A
    track that starts after the picture ends, or an offset past the file's end, is an
    error naming the file."""
    lengths = dict(lengths or {})
    out = []
    for a in tracks:
        if not Path(a.file).is_file():
            raise FileNotFoundError(f"audio: no file {a.file}")
        n = lengths[a.file] if a.file in lengths else ff.length(a.file)
        if a.offset >= n:
            raise ValueError(f"audio {a.file}: offset {a.offset:g} s is past the end of the "
                             f"file ({n:g} s)")
        if a.start >= picture:
            raise ValueError(f"audio {a.file}: starts at {a.start:g} s, after the picture's "
                             f"{picture:g} s")
        out.append(TrackPlan(a, n, a.start, min(picture, a.start + n - a.offset)))
    return out


def audio_graph(plans: list[TrackPlan], first: int, picture: float) -> tuple[list, str]:
    """ffmpeg inputs and a filter graph (ending in ``[a]``) that play ``plans`` under
    a picture of ``picture`` seconds; the tracks are inputs ``first``, ``first + 1``
    ..."""
    inputs, graph, labels = [], [], []
    for k, t in enumerate(plans):
        a = t.audio
        span = t.end - t.start
        fade_in, fade_out = (min(f, span) for f in a.fade)
        chain = [f"atrim=start={a.offset:g}:duration={span:g}", "asetpts=PTS-STARTPTS",
                 f"volume={a.volume:g}"]
        if fade_in:
            chain.append(f"afade=t=in:st=0:d={fade_in:g}")
        if fade_out:
            chain.append(f"afade=t=out:st={span - fade_out:g}:d={fade_out:g}")
        if t.start:
            chain.append(f"adelay=delays={round(t.start * 1000)}:all=1")
        inputs += ["-i", a.file]
        graph.append(f"[{first + k}:a]{','.join(chain)}[t{k}]")
        labels.append(f"[t{k}]")
    mix = f"amix=inputs={len(labels)}:normalize=0:duration=longest," if len(labels) > 1 else ""
    graph.append(f"{''.join(labels)}{mix}aresample=48000,apad=whole_dur={picture:g}[a]")
    return inputs, ";".join(graph)


def build(film, *, folder=None, force: bool = False, mute: bool = False,
          panels: dict | None = None) -> Built:
    """Build ``film`` (a :class:`~flowreel.film.Film` or a film file's path) into its
    ``output``.

    ``folder`` keeps the clips (default ``clips/`` beside the film file); ``force``
    rebuilds every clip; ``mute`` leaves the sound out; ``panels`` are options for
    drawing a layout's ``rate: output`` panels (such as ``jobs``). Returns a
    :class:`Built`."""
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
    args = ["-f", "concat", "-safe", 0, "-i", listing]
    maps = ["-map", "0:v", "-c:v", "copy"]
    notes = []
    if film.audio and not mute:
        plans = plan_tracks(film.audio, measured)
        inputs, graph = audio_graph(plans, 1, measured)
        args += inputs
        maps += ["-filter_complex", graph, "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        for t in plans:
            notes.append(f"audio {Path(t.audio.file).name}: {t.start:.2f} to {t.end:.2f} s "
                         f"of the film (file {t.length:.2f} s)")
    elif film.audio:
        notes.append("audio: muted")
    tmp = out.with_name(out.stem + ".part" + out.suffix)
    ff.run(*args, *maps, "-t", f"{measured:.6f}", "-movflags", "+faststart", tmp)
    os.replace(tmp, out)
    return Built(out, shots, clips.line.length, measured, notes)
