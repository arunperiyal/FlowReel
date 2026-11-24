"""A film of scenes built (plan Section 19.11, Phase 10 branch 3): a clip per scene, kept
by its key, then the film.

**Length.** A scene of ``seconds`` lasts that long. Otherwise it lasts as long as its
main box plays (:class:`Playback`): the box's frames at its ``rate`` (``n / fps``
seconds, each frame shown for a whole step), plus its freezes. A shot box's frames are
its shot's ``frames/<name>`` (rendered beforehand; a missing one stops the build, naming
the shot), a panel box's its panel's ``times``. Every timed box plays from the scene's
start and holds its last frame once it ends.

**Which picture.** On output frame ``j`` (``t = j / fps`` seconds into the scene) a
timed box shows the position ``own(t) * rate`` among its frames, ``own(t)`` being ``t``
less the freezes passed (and stopped at a freeze's ``at`` during it):

- a shot at the film's rate, or under ``to_output: repeat``: the frame there;
- ``blend``: the two frames around it, cross-faded;
- ``interpolate``: a frame of the shot's **base clip**, its frames brought to the film's
  rate by ffmpeg's ``minterpolate`` (:func:`flowreel.film.clips.rate_filter`), scaled to
  the box and kept losslessly (FFV1) by its key under ``clips/``;
- a panel: drawn at the box's size at the time between its two frames, so a plot's dot
  moves smoothly and is never smeared.

**A clip per scene.** Every frame is drawn (:func:`flowreel.film.boxes.draw_frame`),
faded from and to black by the scene's ``fade``, given the watermark when it shows
there, and piped to ffmpeg, encoded as every clip is
(:func:`flowreel.film.clips.encode_args`). The clip's name holds a key of everything in
it (the scene and film settings, each file it reads, the held frame's scene), so a
changed caption rebuilds one scene and the others are kept. Its last frame is kept
beside it, for a ``last_frame`` box of another scene.

**The film.** Scenes follow each other; a scene's ``cross`` dissolves its last ``cross``
seconds into the next scene's first (ffmpeg's ``xfade``), so the film is the sum of the
scenes' lengths less the crosses. Without a cross the clips are joined without encoding
again. Audio, chapters (a scene's ``chapter``, from its start), subtitles (each timed
text box with ``subtitle``) and the preview copy are as for a film of shots
(:mod:`flowreel.film.build`).
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from flowreel.film import ffmpeg as ff
from flowreel.film.model import Box, Film, Scene

#: Bumped when this module changes how clips are made, so old clips are rebuilt.
VERSION = 1
EPS = 1e-9
QUALITY = ("-crf", "14", "-preset", "slow")             # as a finished clip of shots


# ---- playback -----------------------------------------------------------------------

@dataclass(frozen=True)
class Playback:
    """How a timed box plays: ``frames`` at ``fps``, with ``freezes``."""

    frames: int
    fps: float
    freezes: tuple = ()

    @property
    def length(self) -> float:
        """Seconds: every frame for a whole step, and the freezes."""
        return self.frames / self.fps + sum(f.hold for f in self.freezes)

    def own(self, t: float) -> float:
        """Seconds of the box's own frames shown ``t`` seconds into the scene."""
        shift = 0.0
        for f in self.freezes:
            if t - shift < f.at:
                break
            if t - shift < f.at + f.hold:
                return f.at
            shift += f.hold
        return t - shift

    def position(self, t: float) -> float:
        """The position among the frames at ``t`` (0 to ``frames - 1``)."""
        return float(min(max(self.own(t) * self.fps, 0.0), self.frames - 1))


def frame_files(folder: Path) -> list[Path]:
    """A folder's ``frame_00000.png`` ... in order."""
    return sorted(Path(folder).glob("frame_[0-9][0-9][0-9][0-9][0-9].png"))


def _shot_label(box: Box) -> str:
    c = box.content
    return f"shot {c.file}" if c.file is not None else f"frames {c.frames}"


def playback(box: Box, film: Film) -> Playback:
    """The :class:`Playback` of a shot or panel box. Raises ``ValueError`` naming the
    shot when it has no frames, and for a freeze past the box's frames."""
    from flowreel.film.boxes import shot_frames
    c = box.content
    if box.kind == "shot":
        folder = shot_frames(box)
        n = len(frame_files(folder))
        if not n:
            hint = (f"; render it first: flowreel shot render {c.file}" if c.file is not None
                    else "")
            raise ValueError(f"box {box.name!r}: {_shot_label(box)} has no frames in "
                             f"{folder}{hint}")
    elif box.kind == "panel":
        from flowreel.compose.panel_file import frame_times, load
        n = len(frame_times(load(c.file)))
    else:
        raise ValueError(f"box {box.name!r} is a {box.kind}: it has no frames to play")
    p = Playback(n, c.rate.fps, c.freezes)
    own = n / c.rate.fps
    for f in c.freezes:
        if f.at > own + EPS:
            raise ValueError(f"box {box.name!r}: a freeze at {f.at:g} s is past its "
                             f"{own:g} s of frames")
    return p


def scene_length(scene: Scene, film: Film) -> float:
    """A scene's length in seconds: its ``seconds``, else its main box's playback."""
    if scene.seconds is not None:
        return scene.seconds
    return playback(scene.layout.main, film).length


# ---- the plan -----------------------------------------------------------------------

@dataclass(frozen=True)
class Placed:
    """A scene placed in the film: its ``scene``, ``start`` (film seconds), ``length``
    and ``frames`` (its clip's)."""

    scene: Scene
    start: float
    length: float
    frames: int

    @property
    def end(self) -> float:
        """Film seconds where the scene ends."""
        return self.start + self.length


@dataclass(frozen=True)
class Subtitle:
    """A timed text box as a subtitle: film seconds ``start`` to ``end``, ``lines``."""

    start: float
    end: float
    lines: tuple


@dataclass
class Plan:
    """The film laid out: its scenes :class:`Placed`, its ``length``, ``chapters``
    (:class:`~flowreel.film.timeline.TimedChapter`) and ``subtitles``."""

    film: Film
    scenes: list
    length: float
    chapters: list = field(default_factory=list)
    subtitles: list = field(default_factory=list)

    def placed(self, name: str) -> Placed:
        """The scene called ``name``, placed."""
        for p in self.scenes:
            if p.scene.name == name:
                return p
        raise KeyError(f"no scene {name!r} (scenes: {', '.join(p.scene.name for p in self.scenes)})")


def plan(film: Film) -> Plan:
    """Lay ``film`` out (see the module)."""
    from flowreel.film.timeline import TimedChapter
    placed, start = [], 0.0
    for k, scene in enumerate(film.scenes):
        length = scene_length(scene, film)
        if scene.cross > length + EPS:
            raise ValueError(f"scene {scene.name!r}: a cross of {scene.cross:g} s is longer "
                             f"than the scene ({length:g} s)")
        if k and film.scenes[k - 1].cross > length + EPS:
            raise ValueError(f"scene {scene.name!r} is shorter ({length:g} s) than the cross "
                             f"into it ({film.scenes[k - 1].cross:g} s)")
        frames = round(length * film.fps)
        placed.append(Placed(scene, start, frames / film.fps, frames))
        start += frames / film.fps - scene.cross
    total = placed[-1].end
    marks = [(p.start + p.scene.chapter.at, p) for p in placed if p.scene.chapter is not None]
    chapters = [TimedChapter(p.scene.chapter.title, p.scene.name, at,
                             marks[i + 1][0] if i + 1 < len(marks) else total)
                for i, (at, p) in enumerate(marks)]
    subtitles = []
    for p in placed:
        for box in p.scene.layout.boxes:
            if box.kind == "text" and box.at is not None and box.content.subtitle:
                end = p.length if box.at[1] is None else box.at[1]
                subtitles.append(Subtitle(p.start + box.at[0], p.start + end, box.content.lines))
    subtitles.sort(key=lambda s: s.start)
    return Plan(film, placed, total, chapters, subtitles)


# ---- pictures of timed boxes --------------------------------------------------------

def _rect_size(box: Box, film: Film) -> tuple[int, int]:
    x, y, w, h = box.rect(film.size)
    return max(round(w), 1), max(round(h), 1)


class ShotPictures:
    """A shot box's pictures on output frames (see the module)."""

    def __init__(self, box: Box, film: Film, clips: Path):
        from flowreel.film.boxes import shot_frames
        from flowreel.scene.frame_views import load_views
        self.box, self.film = box, film
        self.folder = shot_frames(box)
        self.files = frame_files(self.folder)
        self.play = playback(box, film)
        rate = box.content.rate
        self.ratio = round(film.fps / rate.fps)
        self.mode = "direct" if self.ratio == 1 or rate.to_output == "repeat" else rate.to_output
        self.views = load_views(self.folder)
        self.clips = clips
        self._reader = None

    def key(self) -> dict:
        """What decides the pictures: every frame file, the record, the rate."""
        from flowreel.film.clips import stamp
        record = self.folder / ".views.json"
        return {"frames": [stamp(f) for f in self.files],
                "views": stamp(record) if record.is_file() else None,
                "rate": asdict(self.box.content.rate),
                "freezes": [asdict(f) for f in self.box.content.freezes],
                "size": _rect_size(self.box, self.film) if self.mode == "interpolate" else None}

    def at(self, t: float):
        """``(picture, view)`` ``t`` seconds into the scene."""
        from PIL import Image

        from flowreel.scene.rendering import FRAME_NAME
        pos = self.play.position(t)
        view = self.views.get(FRAME_NAME.format(int(round(pos))))
        if self.mode == "direct":
            return Image.open(self.files[int(math.floor(pos + EPS))]), view
        if self.mode == "blend":
            a = int(math.floor(pos + EPS))
            frac = pos - a
            first = Image.open(self.files[a]).convert("RGB")
            if frac < EPS or a + 1 >= len(self.files):
                return first, view
            return Image.blend(first, Image.open(self.files[a + 1]).convert("RGB"), frac), view
        return self._interpolated(min(int(round(pos * self.ratio)), self._count - 1)), view

    @property
    def _count(self) -> int:
        return len(self.files) * self.ratio

    def base(self) -> Path:
        """The shot's frames at the film's rate, interpolated and scaled to the box: a
        lossless clip kept under ``clips/`` by its key."""
        from flowreel.film.clips import rate_filter
        from flowreel.scene.keys import digest
        key = digest({"version": VERSION, **self.key(), "fps": self.film.fps})[:16]
        path = self.clips / f"base_{self.box.name}_{key}.mkv"
        if path.is_file():
            return path
        first = int(self.files[0].stem.split("_")[1])
        names = [f"frame_{first + k:05d}.png" for k in range(len(self.files))]
        if [f.name for f in self.files] != names:
            raise ValueError(f"box {self.box.name!r}: the frames in {self.folder} are not "
                             f"numbered one after another from {self.files[0].name}")
        w, h = _rect_size(self.box, self.film)
        rate = self.box.content.rate
        tmp = path.with_name(path.stem + ".part.mkv")
        ff.run("-framerate", rate.fps, "-start_number", first,
               "-i", self.folder / "frame_%05d.png",
               "-vf", f"{rate_filter(rate.fps, self.film.fps, rate.to_output)},"
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease",
               "-frames:v", self._count, "-c:v", "ffv1", "-pix_fmt", "bgr0", tmp)
        os.replace(tmp, path)
        return path

    def _interpolated(self, index: int):
        from PIL import Image
        if self._reader is None or index < self._reader[1]:
            self.close()
            path = self.base()
            w, h = (int(v) for v in ff.probe(path, "stream=width,height").split()[:2])
            proc = subprocess.Popen([str(ff.find().ffmpeg), "-v", "error", "-i", str(path),
                                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    stdout=subprocess.PIPE)
            self._reader = [proc, -1, None, (w, h)]
        proc, at, last, (w, h) = self._reader
        while at < index:
            data = proc.stdout.read(w * h * 3)
            if len(data) < w * h * 3:
                break
            last, at = Image.frombytes("RGB", (w, h), data), at + 1
        self._reader[1:3] = [at, last]
        return last

    def close(self) -> None:
        """Stop the base clip's reader."""
        if self._reader is not None:
            self._reader[0].kill()
            self._reader[0].wait()
            self._reader = None


class PanelPictures:
    """A panel box's pictures: drawn at the box's size at the time between its frames."""

    def __init__(self, box: Box, film: Film):
        from flowreel.compose.panel_file import frame_times
        from flowreel.film.boxes import PanelDrawer
        self.box = box
        self.drawer = PanelDrawer(box.content.file, _rect_size(box, film))
        self.times = list(frame_times(self.drawer.panel))
        self.play = playback(box, film)

    def key(self) -> dict:
        """What decides the pictures: the panel's own key, its times, its playback."""
        from flowreel.compose.panels import key_parts
        return {"panel": key_parts(self.drawer.panel, self.drawer.kind), "times": self.times,
                "rate": asdict(self.box.content.rate),
                "freezes": [asdict(f) for f in self.box.content.freezes]}

    def at(self, t: float):
        """``(picture, None)`` ``t`` seconds into the scene."""
        pos = self.play.position(t)
        a = int(math.floor(pos + EPS))
        frac = pos - a
        time = self.times[a] if a + 1 >= len(self.times) or frac < EPS else \
            self.times[a] + (self.times[a + 1] - self.times[a]) * frac
        return self.drawer.at(time), None

    def close(self) -> None:
        """Nothing to stop: a panel is drawn here."""


# ---- a scene's clip -----------------------------------------------------------------

@dataclass(frozen=True)
class SceneClip:
    """A scene's clip: its ``path``, its kept ``last`` frame, and whether it was
    ``built`` now (``False``: kept)."""

    path: Path
    last: Path
    built: bool


def _watermark_on(w, scene: Scene, start: float, t: float) -> bool:
    if w is None:
        return False
    if w.shots is not None:
        return scene.name in w.shots
    if w.seconds is not None:
        return w.seconds[0] - EPS <= start + t < w.seconds[1]
    return True


class SceneBuilder:
    """The clips of one film of scenes, kept in ``folder`` (default ``clips/`` at the
    project root). ``force`` rebuilds every clip asked for."""

    def __init__(self, film: Film, folder=None, force: bool = False, plan_: Plan | None = None):
        from flowreel.project.paths import output
        self.film, self.force = film, force
        self.plan = plan_ or plan(film)
        self.folder = Path(folder) if folder is not None else output(film.folder, "clips")
        self.folder.mkdir(parents=True, exist_ok=True)
        self._clips: dict[str, SceneClip] = {}
        self._keys: dict[str, str] = {}

    def _timed(self, scene: Scene) -> dict:
        out = {}
        for box in scene.layout.boxes:
            if box.kind == "shot":
                out[box.name] = ShotPictures(box, self.film, self.folder)
            elif box.kind == "panel":
                out[box.name] = PanelPictures(box, self.film)
        return out

    def key(self, name: str) -> str:
        """The key of scene ``name``'s clip (see the module)."""
        if name in self._keys:
            return self._keys[name]
        from flowreel.film.clips import stamp
        from flowreel.film.watermark import key_fields
        from flowreel.scene.keys import code_version, digest
        p = self.plan.placed(name)
        scene = p.scene
        files, held, settled = {}, {}, True
        for box in scene.layout.boxes:
            if box.kind == "image":
                files[box.name] = stamp(box.content.file)
            elif box.kind == "last_frame":
                # the held frame's pixels, so a change elsewhere in that scene that leaves
                # its last frame alike rebuilds nothing here
                target = box.content.scene
                last = self.folder / f"scene_{target}_{self.key(target)}.last.png"
                if last.is_file():
                    import hashlib
                    held[box.name] = hashlib.sha256(last.read_bytes()).hexdigest()
                else:
                    held[box.name], settled = "not built: " + self.key(target), False
        timed = self._timed(scene)
        try:
            pictures = {n: t.key() for n, t in timed.items()}
        finally:
            for t in timed.values():
                t.close()
        w = self.film.watermark
        parts = {"version": VERSION, "code": code_version(), "fps": self.film.fps,
                 "size": list(self.film.size), "style": asdict(self.film.style),
                 "scene": asdict(scene), "frames": p.frames, "files": files,
                 "held": held, "pictures": pictures,
                 "watermark": key_fields(w) if w is not None else None,
                 "start": p.start if w is not None and w.seconds is not None else None}
        key = digest(parts)[:16]
        if settled:                    # a key made before its held frame exists may change
            self._keys[name] = key
        return key

    def clip(self, name: str) -> SceneClip:
        """Scene ``name``'s clip, built unless kept (the scenes whose last frame it
        holds first)."""
        if name in self._clips:
            return self._clips[name]
        p = self.plan.placed(name)
        held = {b.name: self.clip(b.content.scene).last for b in p.scene.layout.boxes
                if b.kind == "last_frame"}
        key = self.key(name)
        path = self.folder / f"scene_{name}_{key}.mp4"
        last = path.with_suffix(".last.png")
        if path.is_file() and last.is_file() and not self.force:
            self._clips[name] = SceneClip(path, last, False)
            return self._clips[name]
        self._encode(p, held, path, last)
        self._clips[name] = SceneClip(path, last, True)
        return self._clips[name]

    def frame(self, name: str, j: int, held: dict | None = None, timed: dict | None = None):
        """Output frame ``j`` of scene ``name`` as drawn (before its fades): a Pillow
        image."""
        from flowreel.film.boxes import Contents, draw_frame
        p = self.plan.placed(name)
        t = j / self.film.fps
        contents = Contents(dict(held or {}))
        for box_name, pictures in (timed or {}).items():
            picture, view = pictures.at(t)
            contents.pictures[box_name] = picture
            if view is not None:
                contents.views[box_name] = view
        stills = self.__dict__.setdefault("_stills", {}).setdefault(name, {})
        return draw_frame(self.film, p.scene, t, contents, length=p.length, cache=stills)

    def _encode(self, p: Placed, held: dict, path: Path, last: Path) -> None:
        from flowreel.film.clips import encode_args
        from flowreel.film.watermark import stamp
        film, scene = self.film, p.scene
        w, h = film.size
        tmp = path.with_name(path.stem + ".part.mp4")
        command = [str(ff.find().ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                   "-r", str(film.fps), "-i", "-",
                   "-vf", "scale=out_color_matrix=bt709:out_range=tv,setsar=1",
                   *encode_args(film.fps), *QUALITY, "-frames:v", str(p.frames), str(tmp)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        timed = self._timed(scene)
        fade_in, fade_out = scene.fade
        picture = None
        try:
            for j in range(p.frames):
                picture = np.asarray(self.frame(scene.name, j, held, timed))
                t = j / film.fps
                if _watermark_on(film.watermark, scene, p.start, t):
                    picture = stamp(picture, film.watermark)
                factor = 1.0
                if fade_in > 0:
                    factor = min(factor, t / fade_in)
                if fade_out > 0:
                    factor = min(factor, (p.length - (j + 1) / film.fps) / fade_out)
                factor = min(max(factor, 0.0), 1.0)
                if j == p.frames - 1:
                    from PIL import Image
                    Image.fromarray(picture).save(last)       # unfaded: what a hold shows
                if factor < 1:
                    picture = (picture.astype(float) * factor).round().astype(np.uint8)
                proc.stdin.write(np.ascontiguousarray(picture, np.uint8).tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="replace")
            if proc.wait() != 0:
                raise ff.FfmpegError(f"ffmpeg failed on scene {scene.name!r}:\n{err[-3000:]}")
        except BaseException:
            proc.kill()
            proc.wait()
            tmp.unlink(missing_ok=True)
            raise
        finally:
            for t in timed.values():
                t.close()
        os.replace(tmp, path)


# ---- the film -----------------------------------------------------------------------

def _join(plan_: Plan, clips: list[Path], out: Path, folder: Path) -> list:
    """ffmpeg's inputs and mapping for the picture: the clips joined (see the module)."""
    from flowreel.film.build import concat_list
    if not any(p.scene.cross for p in plan_.scenes[:-1]):
        listing = concat_list(clips, folder / "film_list.txt")
        return ["-f", "concat", "-safe", 0, "-i", listing], ["-map", "0:v", "-c:v", "copy"]
    from flowreel.film.clips import encode_args
    picture = folder / "film_picture.mp4"
    inputs, graph = [], []
    for k, c in enumerate(clips):
        inputs += ["-i", c]
        graph.append(f"[{k}:v]settb=AVTB,setpts=PTS-STARTPTS[s{k}]")   # one timebase for all
    cur = "[s0]"
    for k in range(1, len(clips)):
        before = plan_.scenes[k - 1].scene.cross
        label = f"[v{k}]"
        if before > 0:
            graph.append(f"{cur}[s{k}]xfade=transition=fade:duration={before:g}:"
                         f"offset={plan_.scenes[k].start:.6f}{label}")
        else:
            graph.append(f"{cur}[s{k}]concat=n=2:v=1:a=0{label}")
        cur = label
    ff.run(*inputs, "-filter_complex", ";".join(graph), "-map", cur,
           *encode_args(plan_.film.fps), *QUALITY, picture)
    return ["-i", picture], ["-map", "0:v", "-c:v", "copy"]


def srt_text(plan_: Plan) -> str:
    """The subtitles of ``plan_`` as a SubRip file's text."""
    from flowreel.film.check import plain, srt_time
    return "\n".join(
        f"{k}\n{srt_time(s.start)} --> {srt_time(s.end)}\n"
        + "\n".join(plain(line) for line in s.lines) + "\n"
        for k, s in enumerate(plan_.subtitles, start=1))


def write_srt(plan_: Plan, path: Path | None = None) -> Path:
    """Write the subtitles of ``plan_`` (default beside the film: ``film.srt``)."""
    from flowreel.film.check import srt_path
    path = Path(path) if path is not None else srt_path(plan_.film.output)
    path.write_text(srt_text(plan_), encoding="utf-8")
    return path


def build(film, *, folder=None, force: bool = False, mute: bool = False,
          preview: int | None = None, crf: int | None = None, only: str | None = None):
    """Build a film of scenes into its ``output`` (as
    :func:`flowreel.film.build.build` does a film of shots; ``only`` names a scene).
    Returns a :class:`~flowreel.film.build.Built`, its rows the scenes."""
    from flowreel.film import chapters as ch
    from flowreel.film.build import (PREVIEW_CRF, ShotLength, _check_preview, audio_graph,
                                     only_path, plan_tracks, write_preview)
    Built = scene_built()
    from flowreel.film.model import load
    film = film if isinstance(film, Film) else load(film)
    crf = PREVIEW_CRF if crf is None else crf
    if only is not None:
        film.scene(only)
        if preview is not None:
            raise ValueError("preview: a preview copy is of the whole film, not one scene")
    if preview is not None:
        _check_preview(film, preview, crf)
    builder = SceneBuilder(film, folder, force)
    line = builder.plan
    if only is not None:
        clip = builder.clip(only)
        out = only_path(Path(film.output), only)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip.path, out)
        p = line.placed(only)
        row = ShotLength(only, p.length, ff.length(clip.path), clip.built)
        return Built(out, [row], p.length, row.measured, [], None, None, None)
    rows, paths = [], []
    for p in line.scenes:
        clip = builder.clip(p.scene.name)
        paths.append(clip.path)
        rows.append(ShotLength(p.scene.name, p.length, ff.length(clip.path), clip.built))
    measured = sum(r.measured for r in rows) - sum(p.scene.cross for p in line.scenes[:-1])
    out = Path(film.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    args, maps = _join(line, paths, out, builder.folder)
    notes, youtube = [], None
    if line.chapters:
        meta = builder.folder / "film_chapters.txt"
        meta.write_text(ch.metadata_text(line.chapters, measured), encoding="utf-8")
        args += ["-f", "ffmetadata", "-i", meta]
        maps += ["-map_chapters", 1]
        youtube = ch.chapters_path(out)
        notes += ch.youtube_notes(line.chapters)
    if film.audio and not mute:
        plans = plan_tracks(film.audio, measured)
        inputs, graph = audio_graph(plans, 2 if line.chapters else 1, measured)
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
    copy = write_preview(film, out, preview, crf) if preview is not None else None
    subtitles = write_srt(line) if line.subtitles else None
    if youtube is not None:
        youtube.write_text(ch.youtube_text(line.chapters), encoding="utf-8")
    return Built(out, rows, line.length, measured, notes, copy, subtitles, youtube)


def _scenes_table(lines: list[str]) -> list[str]:
    """A report's lines with its first column headed ``scene``."""
    head = lines[0]
    return [head.replace("shot ", "scene", 1) if head.startswith("shot ") else head] + lines[1:]


def scene_built():
    """:class:`~flowreel.film.build.Built` for a film of scenes: its rows are scenes."""
    from flowreel.film.build import Built

    class SceneBuilt(Built):
        def table(self) -> list[str]:
            return _scenes_table(super().table())
    return SceneBuilt


def lengths(film, *, folder=None):
    """Each scene's planned length and, when its clip is built and current, its
    measured one, without building (``film lengths``): a
    :class:`~flowreel.film.build.Lengths` whose rows are scenes, its measured film the
    clips less the crosses."""
    from flowreel.film.build import Lengths, ShotLength
    from flowreel.film.model import load
    film = film if isinstance(film, Film) else load(film)
    builder = SceneBuilder(film, folder)
    crosses = sum(p.scene.cross for p in builder.plan.scenes[:-1])

    class SceneLengths(Lengths):
        @property
        def measured(self):
            total = Lengths.measured.fget(self)
            return None if total is None else total - crosses

        def table(self):
            return _scenes_table(super().table())

    rows = []
    for p in builder.plan.scenes:
        path = builder.folder / f"scene_{p.scene.name}_{builder.key(p.scene.name)}.mp4"
        rows.append(ShotLength(p.scene.name, p.length,
                               ff.length(path) if path.is_file() else None, False))
    return SceneLengths(rows, builder.plan.chapters, builder.plan.length)


def contact(film, at: str = "caption", path: Path | None = None, *, columns: int = 4,
            width: int = 480, folder=None, force: bool = False) -> Path:
    """The contact sheet of a film of scenes (as :func:`flowreel.film.check.contact`):
    stills at the middle of each timed text box (``caption``), of each freeze of a main
    box (``freeze``), or ``every:S`` seconds, from the scenes' clips."""
    from PIL import Image, ImageDraw

    from flowreel.film.cards import font
    from flowreel.film.check import contact_path, grab, plain
    from flowreel.film.model import load
    film = film if isinstance(film, Film) else load(film)
    builder = SceneBuilder(film, folder, force)
    line = builder.plan
    stills = []                                   # (film time, scene, why)
    if at == "caption":
        for p in line.scenes:
            for box in p.scene.layout.boxes:
                if box.kind == "text" and box.at is not None:
                    end = p.length if box.at[1] is None else box.at[1]
                    stills.append((p.start + (box.at[0] + end) / 2, p, plain(box.content.lines[0])))
    elif at == "freeze":
        for p in line.scenes:
            main = p.scene.layout.main
            shift = 0.0
            for f in (main.content.freezes if main is not None else ()):
                stills.append((p.start + f.at + shift + f.hold / 2, p, "freeze"))
                shift += f.hold
    elif at.startswith("every:"):
        try:
            step = float(at.split(":", 1)[1])
        except ValueError:
            step = 0.0
        if not step > 0:
            raise ValueError(f"contact: 'every:S' needs a number of seconds above 0, got {at!r}")
        for k in range(math.ceil(line.length / step - EPS)):
            t = k * step
            p = next((q for q in reversed(line.scenes) if q.start <= t + EPS), line.scenes[0])
            stills.append((t, p, ""))
    else:
        raise ValueError(f"contact: at is 'caption', 'freeze' or 'every:S', got {at!r}")
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
    for k, (t, p, why) in enumerate(stills):
        frame = min(int((t - p.start) * film.fps + EPS), p.frames - 1)
        image = grab(builder.clip(p.scene.name).path, frame, (w, h))
        x = gap + (k % cols) * (w + gap)
        y = gap + (k // cols) * cell
        sheet.paste(image, (x, y))
        text = f"{t:.2f} s  {p.scene.name}" + (f"  {why}" if why else "")
        while draw.textlength(text, font=fnt) > w and len(text) > 4:
            text = text[:-2] + "…"
        draw.text((x, y + h + label * 0.4), text, font=fnt, fill=(220, 220, 220))
    path = Path(path) if path is not None else contact_path(film.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path
