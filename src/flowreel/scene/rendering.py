"""Render a shot to frames (plan Section 7.5).

:func:`render_frame` draws one frame in this process and returns the picture.
:func:`render` draws many into ``frames/<shot>/frame_00000.png``, each in a fresh
process, ``jobs`` at a time. A process per frame is the prototype's way and is kept on
purpose: VTK and the readers do not give all memory back, so a long render in one process
grows until the machine swaps, and memory per frame (not cores) limits ``jobs``.
"""
from __future__ import annotations

import multiprocessing
import os
import time as _time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from flowreel.jobs.resources import resources
from flowreel.scene import backend as backend_mod
from flowreel.scene.cache import SurfaceCache
from flowreel.scene.camera import shot_camera
from flowreel.scene.errors import Checker
from flowreel.scene.keys import KeyStore, frame_key
from flowreel.scene.layers import Frame, FrameData
from flowreel.scene.lights import apply_lights
from flowreel.scene.plan import FramePlan, plan
from flowreel.scene.shot import CropAround, Shot, load
from flowreel.tracks import parse_colour

FRAME_NAME = "frame_{:05d}.png"
CACHE_FOLDER = ".cache/surfaces"


def open_source(shot: Shot):
    """The source named by the shot's ``source``.

    ``adapter:location``: ``geometry:NAME`` names a body; other adapters get the
    location as ``path``. The mapping form passes its keys to the adapter as options.
    A relative ``path``, and a relative ``body`` file (or mapping of them) for any
    adapter but ``geometry``, is taken from the shot file's folder.
    """
    from flowreel import sources
    return sources.create(shot.source[0], **source_options(shot))


def source_options(shot: Shot) -> dict:
    """The options :func:`open_source` gives the adapter, with paths resolved."""
    adapter, location = shot.source
    if not shot.source_options:
        options = {"body": location} if adapter == "geometry" else {"path": location}
    else:
        options = dict(shot.source_options)
    if "path" in options:
        options["path"] = _beside(shot, options["path"])
    if adapter != "geometry" and "body" in options:
        body = options["body"]
        options["body"] = {k: _beside(shot, v) for k, v in body.items()} \
            if isinstance(body, dict) else _beside(shot, body)
    return options


def _beside(shot: Shot, value):
    """``value`` (a path) taken from the shot file's folder when relative."""
    if not isinstance(value, str) or not shot.file:
        return value
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else Path(shot.file).parent / path)


def source_id(shot: Shot) -> list:
    """The shot's source as it goes into keys: the adapter and its options with paths
    resolved, so two shot files that write the same relative path for different data
    (``flow_*.vti`` in two folders) never share a cached surface or a frame key."""
    return [shot.source[0], source_options(shot)]


def bind_series(shot: Shot, source, fp: FramePlan) -> None:
    """Give every series track of the shot's layers the source and the time of each
    frame (the time of the step it shows)."""
    from flowreel.tracks import SeriesTrack
    series = [(layer, name, t) for layer in shot.layers for name, t in layer.tracks.items()
              if isinstance(t, SeriesTrack)]
    if not series:
        return
    times = [fp.times[fp.time.step(i)] for i in range(fp.n_frames)]
    for layer, name, track in series:
        check = Checker(shot.file, ("layers", shot.layers.index(layer), name))
        try:
            track.bind(source, times)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            message = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
            raise check.error(str(message).removeprefix(f"{name}: ")) from None


def _as_shot(shot) -> Shot:
    return shot if isinstance(shot, Shot) else load(shot)


@dataclass
class Scene:
    """Everything needed to draw any frame of a shot, made once per render.

    Build with :meth:`make`. ``size`` is the picture's ``(width, height)``; when it
    differs from the shot's (a draft), :meth:`values` scales the options given in pixels
    by the ratio of the heights, so lines keep their look.
    """

    shot: Shot
    source: object
    plan: FramePlan
    camera: object
    size: tuple[int, int]
    cache: SurfaceCache | None = None

    @classmethod
    def make(cls, shot, source=None, views=None, tracks=None, size=None,
             cache: str | Path | None = None) -> "Scene":
        """Load ``shot`` (a :class:`Shot` or a path), open its source (unless given) and
        plan it. ``views``/``tracks`` default to the shot's ``cameras.yml``. ``cache`` is
        the surface cache folder, used only when the shot is frozen.

        The source is seen through the bodies of the shot's project (the nearest
        ``flowreel.yml``, :func:`flowreel.project.find_project`), so body names in the
        shot are the declared ones. A source given already wrapped
        (:func:`flowreel.project.names.declare`) is used as it is."""
        from flowreel.project import project_for
        from flowreel.project.names import bodies_key, declare, DeclaredSource
        shot = _as_shot(shot)
        source = source if source is not None else open_source(shot)
        if not isinstance(source, DeclaredSource):
            source = declare(source, project_for(shot.file))
        fp = plan(shot, source)
        bind_series(shot, source, fp)
        camera = shot_camera(shot, views, tracks, rest_step=fp.time.step(0))
        declared = bodies_key(source)
        key_source = source_id(shot) + ([{"bodies": declared}] if declared else [])
        surfaces = SurfaceCache(cache, key_source) if cache is not None and fp.frozen else None
        return cls(shot, source, fp, camera, tuple(size or shot.size), surfaces)

    @property
    def pixel_scale(self) -> float:
        """Picture height over the shot's height: 1 at full size, 0.5 for half."""
        return self.size[1] / self.shot.size[1]

    def values(self, index: int) -> list[dict]:
        """Every layer's option values at frame ``index``, pixel sizes scaled."""
        out = []
        for layer in self.shot.layers:
            v = layer.values(index)
            if self.pixel_scale != 1:
                for opt in layer.options:
                    if opt.pixels and v.get(opt.name) is not None:
                        v[opt.name] = v[opt.name] * self.pixel_scale
            out.append(v)
        return out

    def crop(self, index: int):
        """The box read from the source for frame ``index``: the shot's crop, or for a
        crop that travels with a body (``around``), that frame's box; ``None`` for the
        whole domain."""
        crop = self.shot.crop
        if not isinstance(crop, CropAround):
            return crop
        boxes = self.__dict__.setdefault("_crops", {})
        if index not in boxes:
            boxes[index] = crop.box(index, self.source, self.plan.time.step(index))
        return boxes[index]

    def data(self, index: int) -> FrameData:
        """The data of frame ``index`` (flow read on first use)."""
        return FrameData(self.source, self.plan.time.step(index), crop=self.crop(index),
                         cache=self.cache)

    def draw(self, index: int) -> np.ndarray:
        """Draw frame ``index``: ``(height, width, 3)`` uint8."""
        import pyvista as pv
        if not 0 <= index < self.plan.n_frames:
            raise IndexError(f"frame {index} is outside 0..{self.plan.n_frames - 1}")
        shot = self.shot
        data = self.data(index)
        view = self.camera.view(index, data)
        plotter = pv.Plotter(off_screen=True, window_size=list(self.size))
        try:
            plotter.set_background(_background(shot.background))
            view.apply(plotter.camera)
            if shot.lights is not None:
                apply_lights(plotter, shot.lights, view)
            if shot.antialias != "none":
                plotter.enable_anti_aliasing(shot.antialias)
            self.populate(plotter, index, data=data)
            picture = np.asarray(plotter.screenshot(return_img=True))[:, :, :3]
        finally:
            plotter.close()
        if shot.watermark is not None:
            from flowreel.film.watermark import stamp
            picture = stamp(picture, shot.watermark, self.pixel_scale)
        return picture


    def populate(self, plotter, index: int, step: int | None = None, data=None) -> None:
        """Add the layers of frame ``index`` to ``plotter``, stretched as the shot says:
        what :meth:`draw` draws, without the camera, lights, background or watermark.
        ``step`` shows another time step with frame ``index``'s layer values (the camera
        editor); ``data`` is the frame's :class:`FrameData` when already made."""
        shot = self.shot
        step = self.plan.time.step(index) if step is None else step
        if data is None:
            data = (self.data(index) if step == self.plan.time.step(index) else
                    FrameData(self.source, step, crop=self.crop(index), cache=self.cache))
        from flowreel.scene.drawn import drawing
        with drawing(plotter.renderer, shot.stretch.scale if shot.stretch else None):
            for layer, values in zip(shot.layers, self.values(index)):
                layer.draw(plotter, Frame(index, step, self.plan.times[step], data, values))
        if shot.stretch is not None:
            self._stretch(plotter)

    def _stretch(self, plotter) -> None:
        """Scale every 3D actor by the shot's stretch (about the origin, so the scene
        keeps its layout) and write the note."""
        from vtkmodules.vtkRenderingCore import vtkProp3D
        st = self.shot.stretch
        for actor in plotter.renderer.actors.values():
            if isinstance(actor, vtkProp3D):
                actor.SetScale(*st.scale)
        if st.note:
            from flowreel.scene.text import corner_text
            corner_text(plotter, st.note, st.corner, st.size * self.pixel_scale, st.colour,
                        self.size)


def draft_size(shot_size: tuple[int, int], scale: float | None = None,
               size: tuple[int, int] | None = None) -> tuple[int, int]:
    """The picture size of a render: the shot's, ``size``, or the shot's times ``scale``.

    A scaled size is rounded to even numbers of pixels (at least 2), because video
    encoders need even sides. Give ``scale`` or ``size``, not both.
    """
    if scale is not None and size is not None:
        raise ValueError("give scale or size, not both")
    if size is not None:
        w, h = (int(x) for x in size)
        if w < 1 or h < 1:
            raise ValueError(f"size must be positive, got {w} x {h}")
        return w, h
    if scale is None:
        return tuple(shot_size)
    if not scale > 0:
        raise ValueError(f"scale must be positive, got {scale}")
    return tuple(max(2, 2 * round(n * scale / 2)) for n in shot_size)


def frame_folder(out: str | Path, shot: Shot, size: tuple[int, int]) -> Path:
    """``out/<shot>`` at the shot's size, ``out/<shot>@<W>x<H>`` for a draft, so draft
    frames never mix with the full-size ones (plan Section 7.5)."""
    name = shot.name if tuple(size) == tuple(shot.size) else f"{shot.name}@{size[0]}x{size[1]}"
    return Path(out) / name


def render_frame(shot, frame: int, source=None, *, views=None, tracks=None,
                 size: tuple[int, int] | None = None, scale: float | None = None,
                 backend: str = "auto") -> np.ndarray:
    """Draw frame ``frame`` (0-based) of ``shot`` in this process.

    ``shot`` is a :class:`~flowreel.scene.shot.Shot` or a shot file path; ``source``
    defaults to the shot's own (:func:`open_source`); ``views`` and ``tracks`` to the
    ``cameras.yml`` beside the shot file. ``size`` (``(width, height)``) or ``scale``
    draws a draft (:func:`draft_size`); by default the shot's size. ``backend`` is chosen as in :func:`render`, so a frame drawn here and the same frame
    drawn by a render are the same picture. Returns ``(height, width, 3)`` uint8.
    """
    shot = _as_shot(shot)
    scene = Scene.make(shot, source, views, tracks, draft_size(shot.size, scale, size))
    with _environment(backend_mod.environment(backend_mod.choose(backend))):
        return scene.draw(frame)


@dataclass
class FrameResult:
    """One frame of a :func:`render`: its index, the file, ``status`` (``rendered``, or
    ``skipped`` when the file was already drawn with the same key), the seconds it took
    and the peak memory of its process in bytes (0 in-process or skipped)."""

    index: int
    path: Path
    status: str
    seconds: float = 0.0
    peak_bytes: int = 0


@dataclass
class RenderReport:
    """What :func:`render` did: the frame folder, the backend and one
    :class:`FrameResult` per frame asked for, in frame order."""

    folder: Path
    backend: str | None
    frames: list[FrameResult] = field(default_factory=list)

    def count(self, status: str) -> int:
        """Number of frames with ``status``."""
        return sum(f.status == status for f in self.frames)


def default_threads(jobs: int) -> int:
    """Threads per job when not given: a few, and no more than the cores allow (the
    job's cores in a Slurm job, :func:`flowreel.jobs.resources.resources`)."""
    return max(1, min(4, resources().cores // max(jobs, 1)))


def render(shot, frames: Iterable[int] | None = None, source=None, *, views=None,
           tracks=None, out: str | Path = "frames", jobs: int = 1,
           threads: int | None = None, backend: str = "auto", force: bool = False,
           scale: float | None = None, size: tuple[int, int] | None = None,
           processes: bool = True, progress: Callable[[FrameResult], None] | None = None,
           check_memory: bool = True) -> RenderReport:
    """Render ``frames`` (default all) of ``shot`` to PNG files.

    Frames go to ``out/<shot name>/frame_00000.png``. A frame whose file exists and was
    drawn with the same key (plan Section 11, :mod:`flowreel.scene.keys`) is skipped;
    every frame asked for has its camera recorded in the folder (:func:`record_views`);
    ``force`` draws every frame asked for again. ``scale`` or ``size`` draws a draft:
    the same shot with fewer pixels (:func:`draft_size`), into ``out/<shot>@<W>x<H>/``.
    ``jobs`` frames are drawn at a time,
    each in its own process (``processes=False`` draws them here, one by one, for
    debugging). ``threads`` caps the threads of each job (default
    :func:`default_threads`). ``backend`` is one of
    :data:`flowreel.scene.backend.BACKENDS`. ``source`` must pickle when
    ``processes`` is true. ``progress`` is called with each finished
    :class:`FrameResult`. ``check_memory`` refuses, before drawing, a render whose jobs
    would not fit in the free memory (:func:`flowreel.scene.memory.check_fits`), with
    the ``jobs`` that would. Returns a :class:`RenderReport`.
    """
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    shot = _as_shot(shot)
    size = draft_size(shot.size, scale, size)
    cache = Path(out) / CACHE_FOLDER
    scene = Scene.make(shot, source, views, tracks, size, cache=cache)
    indices = _frames(frames, scene.plan.n_frames, shot)
    if check_memory:
        from flowreel.scene.memory import check_fits
        check_fits(scene, indices, jobs if processes else 1)
    folder = frame_folder(out, shot, size)
    folder.mkdir(parents=True, exist_ok=True)
    threads = threads or default_threads(jobs)
    chosen = backend_mod.choose(backend)
    report = RenderReport(folder, chosen)
    results: dict[int, FrameResult] = {}
    store = KeyStore(folder)
    keys = {i: frame_key(scene, i) for i in indices}
    record_views(scene, indices, folder)

    def done(result: FrameResult):
        results[result.index] = result
        if result.status == "rendered":
            store.put(result.path.name, keys[result.index])
        if progress:
            progress(result)

    todo = []
    for i in indices:
        path = folder / FRAME_NAME.format(i)
        if not force and store.fresh(path, keys[i]):
            done(FrameResult(i, path, "skipped"))
        else:
            todo.append(i)
    with _environment(backend_mod.environment(chosen, threads)):
        if not processes:
            for i in todo:
                done(_draw_to_file(scene, i, folder / FRAME_NAME.format(i)))
        elif todo:
            job = _Job(shot, source, views, tracks, size, str(cache))
            ctx = multiprocessing.get_context("spawn")
            # A frozen shot draws its first frame alone, so that it fills the surface
            # cache and the other jobs read it instead of all contouring at once.
            batches = [todo[:1], todo[1:]] if scene.plan.frozen else [todo]
            with ProcessPoolExecutor(max_workers=min(jobs, len(todo)), mp_context=ctx,
                                     max_tasks_per_child=1) as pool:
                for batch in batches:
                    futures = [pool.submit(_worker, job, i, str(folder / FRAME_NAME.format(i)))
                               for i in batch]
                    for fut in as_completed(futures):
                        done(fut.result())
    report.frames = [results[i] for i in indices]
    drawn = [r for r in report.frames if r.status == "rendered"]
    if processes and drawn:          # for sizing the next render (flowreel.jobs.measured)
        from flowreel.jobs import measured
        record = measured.from_frames([r.peak_bytes for r in drawn],
                                      [r.seconds for r in drawn], threads)
        if record is not None:
            measured.save(folder, record)
    return report


def record_views(scene: Scene, indices, folder: Path) -> None:
    """Record in ``folder`` the view, size and stretch of frames ``indices`` of
    ``scene`` (:mod:`flowreel.scene.frame_views`), for captions anchored in the model."""
    from flowreel.scene.frame_views import DrawnView, save_views
    stretch = None if scene.shot.stretch is None else tuple(scene.shot.stretch.scale)
    save_views(folder, {FRAME_NAME.format(i): DrawnView(scene.camera.view(i, scene.data(i)),
                                                         tuple(scene.size), stretch)
                        for i in indices})


def missing(shot, frames: Iterable[int] | None = None, source=None, *, views=None,
            tracks=None, out: str | Path = "frames", scale: float | None = None,
            size: tuple[int, int] | None = None) -> list[int]:
    """The frames among ``frames`` (default all) of ``shot`` that :func:`render` would
    draw: no file, or one drawn with another key. Nothing is drawn; the source is
    opened to work out the keys."""
    shot = _as_shot(shot)
    size = draft_size(shot.size, scale, size)
    scene = Scene.make(shot, source, views, tracks, size, cache=Path(out) / CACHE_FOLDER)
    folder = frame_folder(out, shot, size)
    store = KeyStore(folder)
    return [i for i in _frames(frames, scene.plan.n_frames, shot)
            if not store.fresh(folder / FRAME_NAME.format(i), frame_key(scene, i))]


def _frames(frames, n: int, shot: Shot) -> list[int]:
    if frames is None:
        return list(range(n))
    out = sorted(set(int(i) for i in frames))
    bad = [i for i in out if not 0 <= i < n]
    if bad:
        raise Checker(shot.file).error(f"frame {bad[0]} is outside the shot's 0..{n - 1}")
    return out


@dataclass
class _Job:
    """What a worker process needs to rebuild the scene (everything pickles)."""

    shot: Shot
    source: object
    views: dict | None
    tracks: dict | None
    size: tuple[int, int]
    cache: str | None = None


def _worker(job: _Job, index: int, path: str) -> FrameResult:
    scene = Scene.make(job.shot, job.source, job.views, job.tracks, job.size, cache=job.cache)
    result = _draw_to_file(scene, index, Path(path))
    result.peak_bytes = peak_memory()
    return result


def _draw_to_file(scene: Scene, index: int, path: Path) -> FrameResult:
    from PIL import Image
    start = _time.perf_counter()
    picture = scene.draw(index)
    tmp = path.with_name(path.stem + ".part.png")
    Image.fromarray(picture).save(tmp)
    os.replace(tmp, path)      # a frame file is never half written
    return FrameResult(index, path, "rendered", _time.perf_counter() - start)


def peak_memory() -> int:
    """Peak resident memory of this process so far, in bytes (Linux and macOS)."""
    import resource
    import sys
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


@contextmanager
def _environment(env: dict[str, str]):
    """Set ``env`` while the block runs (spawned workers inherit it), then restore."""
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _background(value):
    return tuple(parse_colour(value)) if isinstance(value, str) and value.startswith("#") \
        else value
