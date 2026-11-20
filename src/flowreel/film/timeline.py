"""The film's timeline: when each shot starts, how long it lasts, when captions show.

Three clocks are kept apart (plan Section 3): a shot's **frames** count its pictures
from 0, at the shot's own rate; **seconds** are film time. A frames or layout shot of
``n`` frames at ``fps`` frames a second lasts ``n / fps`` seconds plus its freezes; a
card or a hold lasts its ``seconds``.

**Freezes.** A freeze at ``at`` seconds stops on frame ``min(round(at * fps), n - 1)``
and shows it for ``hold`` seconds (``round(hold * fps)`` more frames at the shot's
rate); times after it move on by ``hold``, so the freeze starts at ``at`` plus the
holds before it. These are the AFMS film's rules (``make_film.py``), so its lengths come
out the same.

**Captions.** A shot's caption ``at: [start, end]`` counts from the start of the
finished shot, freezes included; ``end`` left out runs to the shot's end, and ``{shot:
NAME, at: S}`` ends ``S`` seconds into a later shot. A freeze's captions count from
the start of the freeze. :func:`timeline` checks every time against the lengths and
gives each caption its start and end in film seconds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.film.schema import Film, Shot
from flowreel.film.text import Caption, Later
from flowreel.scene.errors import Checker

EPS = 1e-9


@dataclass(frozen=True)
class TimedFreeze:
    """A freeze placed: on frame ``frame`` (of the shot's own frames), starting
    ``start`` seconds into the finished shot, for ``hold`` seconds, ``frames`` more
    frames at the shot's rate."""

    frame: int
    start: float
    hold: float
    frames: int


@dataclass
class TimedShot:
    """A shot placed in the film: ``start`` and ``length`` in seconds; for frames and
    layout shots, its ``frames`` count, ``fps``, ``freezes`` and ``order`` (the frame
    shown at each step of the shot's rate, frozen frames repeated)."""

    shot: Shot
    start: float
    length: float
    frames: int | None = None
    fps: float | None = None
    freezes: list[TimedFreeze] = field(default_factory=list)
    order: list[int] = field(default_factory=list)

    @property
    def end(self) -> float:
        """When the shot ends, in film seconds."""
        return self.start + self.length

    def positions(self, film_fps: int) -> list[float]:
        """The shot's output frames as positions among its own frames, for
        :func:`flowreel.compose.layout` (``output=``) to draw ``rate: output`` panels at.

        Each frame of ``order`` lasts ``film_fps / fps`` output frames; output frame
        ``j`` lies that share of the way from one shown frame to the next, and stays put
        through a freeze, where both are the same frame (the AFMS film's
        ``plots_for``). There are ``length * film_fps`` of them, one per output frame of
        the finished shot."""
        if self.fps is None:
            raise ValueError(f"shot {self.shot.name!r} is a {self.shot.kind}; it has no frames")
        ratio = round(film_fps / self.fps)
        out = []
        for k, a in enumerate(self.order):
            b = self.order[min(k + 1, len(self.order) - 1)]
            out += [a + (b - a) * part / ratio for part in range(ratio)]
        return out


@dataclass(frozen=True)
class TimedCaption:
    """A caption placed: on shot ``shot`` (where it starts), from ``start`` to ``end``
    in film seconds (it may end in a later shot)."""

    caption: Caption
    shot: str
    start: float
    end: float


@dataclass
class Timeline:
    """The film laid out: ``shots`` in order, ``captions`` by start, ``length`` in
    seconds."""

    film: Film
    shots: list[TimedShot]
    captions: list[TimedCaption]

    @property
    def length(self) -> float:
        """The film's planned length in seconds."""
        return self.shots[-1].end if self.shots else 0.0

    def shot(self, name: str) -> TimedShot:
        """The placed shot called ``name``."""
        for s in self.shots:
            if s.shot.name == name:
                return s
        raise KeyError(f"no shot {name!r}")

    def captions_on(self, name: str) -> list[TimedCaption]:
        """The captions showing during shot ``name``, including ones from earlier shots
        that run across the cut."""
        s = self.shot(name)
        return [c for c in self.captions if c.start < s.end - EPS and c.end > s.start + EPS]


def frame_count(shot: Shot) -> int:
    """How many frames a frames or layout shot has: the frame files in its folder, or
    the composed frames its layout will have (its tiles' frames, its panels' times, its
    stations' shots)."""
    from flowreel.compose.frames import frame_files
    if shot.kind == "frames":
        found = frame_files(shot.source)
        if not found:
            raise ValueError(f"shot {shot.name!r}: no frame_NNNNN.png files in {shot.source}")
        return max(found) + 1
    if shot.kind != "layout":
        raise ValueError(f"shot {shot.name!r} is a {shot.kind}; it has no frames")
    return layout_frames(shot.source)


def layout_frames(path: Path) -> int:
    """The number of composed frames a layout file will have, without composing it."""
    from flowreel.compose import load
    from flowreel.compose.frames import frame_files
    from flowreel.compose.panel_file import frame_times, load as load_panel
    lay = load(path)
    counts = []
    for tile in lay.tiles:
        if tile.panel is not None:
            counts.append(len(frame_times(load_panel(tile.panel))))
        elif tile.shot is not None:
            from flowreel.project import project_for
            from flowreel.project.names import declare
            from flowreel.scene.plan import plan
            from flowreel.scene.rendering import open_source
            source = declare(open_source(tile.shot), project_for(tile.shot.file))
            counts.append(plan(tile.shot, source).n_frames)
        else:
            found = frame_files(tile.frames)
            counts.append(max(found) + 1 if found else 0)
    if not counts or max(counts) == 0:
        raise ValueError(f"layout {path} has no frames yet")
    return max(counts)


def timeline(film: Film, counts: dict[str, int] | None = None) -> Timeline:
    """Lay out ``film``. ``counts`` gives the frame count of frames and layout shots by
    name; shots not in it are counted (:func:`frame_count`). Raises
    :class:`~flowreel.scene.errors.ConfigError` for a caption or freeze outside its
    shot."""
    counts = dict(counts or {})
    check = Checker(film.file)
    shots, start = [], 0.0
    for i, shot in enumerate(film.shots):
        at = check.at("shots", i)
        if shot.kind in ("card", "hold"):
            shots.append(TimedShot(shot, start, shot.seconds))
        else:
            if shot.name not in counts:
                try:
                    counts[shot.name] = frame_count(shot)
                except ValueError as exc:
                    raise at.error(str(exc)) from None
            shots.append(_frames_shot(shot, start, counts[shot.name], at))
        start = shots[-1].end
        _check_fade(shots[-1], at)
    names = [s.shot.name for s in shots]
    captions = []
    for i, ts in enumerate(shots):
        at = check.at("shots", i)
        for k, c in enumerate(ts.shot.text):
            captions.append(_place(c, ts, shots, names, at.at("text", k)))
        for j, (fr, tf) in enumerate(zip(ts.shot.freezes, ts.freezes)):
            for k, c in enumerate(fr.text):
                where = at.at("freezes", j, "text", k)
                if c.end > tf.hold + EPS:
                    raise where.error(f"{_name(c)} ends at {c.end:g} s, after the freeze's "
                                      f"{tf.hold:g} s")
                base = ts.start + tf.start
                captions.append(TimedCaption(c, ts.shot.name, base + c.start, base + c.end))
    captions.sort(key=lambda c: c.start)
    return Timeline(film, shots, captions)


def _frames_shot(shot: Shot, start: float, n: int, check: Checker) -> TimedShot:
    fps = shot.rate.fps
    freezes, order, done, shift = [], [], 0, 0.0
    for j, fr in enumerate(shot.freezes):
        if fr.at > n / fps + EPS:
            raise check.at("freezes", j, "at").error(
                f"the freeze at {fr.at:g} s is past the shot's {n / fps:g} s of frames")
        stop = min(round(fr.at * fps), n - 1)
        if stop < done:
            raise check.at("freezes", j, "at").error(
                f"two freezes stop on frame {stop}; move one")
        held = round(fr.hold * fps)
        freezes.append(TimedFreeze(stop, fr.at + shift, fr.hold, held))
        order += list(range(done, stop + 1)) + [stop] * held
        done = stop + 1
        shift += fr.hold
    order += list(range(done, n))
    return TimedShot(shot, start, n / fps + shift, n, fps, freezes, order)


def _check_fade(ts: TimedShot, check: Checker) -> None:
    fade_in, fade_out = ts.shot.fade
    out_at = ts.shot.fade_out_at
    starts = out_at if out_at is not None else ts.length - fade_out
    if fade_in > ts.length + EPS or starts < -EPS or starts + fade_out > ts.length + EPS:
        raise check.at("fade").error(f"the fades run past the shot's {ts.length:g} s")


def _name(c: Caption) -> str:
    return f"caption {c.lines[0]!r}"


def _place(c: Caption, ts: TimedShot, shots: list[TimedShot], names: list[str],
           check: Checker) -> TimedCaption:
    if c.start >= ts.length - EPS:
        raise check.error(f"{_name(c)} starts at {c.start:g} s, at or after the end of shot "
                          f"{ts.shot.name!r} ({ts.length:g} s)")
    if c.end is None:
        end = ts.end
    elif isinstance(c.end, Later):
        if c.end.shot not in names:
            raise check.error(f"{_name(c)} ends in shot {c.end.shot!r}, which the film does "
                              f"not have (shots: {', '.join(names)})")
        other = shots[names.index(c.end.shot)]
        if other.start <= ts.start:
            raise check.error(f"{_name(c)} ends in shot {c.end.shot!r}, which does not come "
                              f"after {ts.shot.name!r}")
        if c.end.at > other.length + EPS:
            raise check.error(f"{_name(c)} ends {c.end.at:g} s into {c.end.shot!r}, after its "
                              f"{other.length:g} s")
        end = other.start + c.end.at
    else:
        if c.end > ts.length + EPS:
            raise check.error(f"{_name(c)} ends at {c.end:g} s, after the end of shot "
                              f"{ts.shot.name!r} ({ts.length:g} s); end it with "
                              "{shot: NAME, at: S} to run across the cut")
        end = ts.start + c.end
    return TimedCaption(c, ts.shot.name, ts.start + c.start, end)
