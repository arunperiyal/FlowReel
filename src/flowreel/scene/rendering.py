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

from flowreel.scene import backend as backend_mod
from flowreel.scene.camera import shot_camera
from flowreel.scene.errors import Checker
from flowreel.scene.layers import Frame, FrameData
from flowreel.scene.lights import apply_lights
from flowreel.scene.plan import FramePlan, plan
from flowreel.scene.shot import Shot, load
from flowreel.tracks import parse_colour

FRAME_NAME = "frame_{:05d}.png"


def open_source(shot: Shot):
    """The source named by ``shot.source`` (``adapter:location``).

    A relative location is taken from the shot file's folder. ``geometry:NAME`` names a
    body; other adapters get the location as ``path``. Sources that need more options
    (a vtk source's body file) are built in code and passed to the render functions.
    """
    from flowreel import sources
    adapter, location = shot.source
    if adapter == "geometry":
        return sources.create(adapter, body=location)
    path = Path(location)
    if not path.is_absolute() and shot.file:
        path = Path(shot.file).parent / path
    return sources.create(adapter, path=str(path))


def _as_shot(shot) -> Shot:
    return shot if isinstance(shot, Shot) else load(shot)


@dataclass
class Scene:
    """Everything needed to draw any frame of a shot, made once per render.

    Build with :meth:`make`. ``size`` is the picture's ``(width, height)``.
    """

    shot: Shot
    source: object
    plan: FramePlan
    camera: object
    size: tuple[int, int]

    @classmethod
    def make(cls, shot, source=None, views=None, tracks=None, size=None) -> "Scene":
        """Load ``shot`` (a :class:`Shot` or a path), open its source (unless given) and
        plan it. ``views``/``tracks`` default to the shot's ``cameras.yml``."""
        shot = _as_shot(shot)
        source = source if source is not None else open_source(shot)
        fp = plan(shot, source)
        camera = shot_camera(shot, views, tracks, rest_step=fp.time.step(0))
        return cls(shot, source, fp, camera, tuple(size or shot.size))

    def data(self, index: int) -> FrameData:
        """The data of frame ``index`` (flow read on first use)."""
        return FrameData(self.source, self.plan.time.step(index), crop=self.shot.crop)

    def draw(self, index: int) -> np.ndarray:
        """Draw frame ``index``: ``(height, width, 3)`` uint8."""
        import pyvista as pv
        if not 0 <= index < self.plan.n_frames:
            raise IndexError(f"frame {index} is outside 0..{self.plan.n_frames - 1}")
        shot, frame = self.shot, self.plan.frame(index)
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
            for layer, values in zip(shot.layers, frame.values):
                layer.draw(plotter, Frame(frame.index, frame.step, frame.time, data, values))
            return np.asarray(plotter.screenshot(return_img=True))[:, :, :3]
        finally:
            plotter.close()


def render_frame(shot, frame: int, source=None, *, views=None, tracks=None,
                 size: tuple[int, int] | None = None, backend: str = "auto") -> np.ndarray:
    """Draw frame ``frame`` (0-based) of ``shot`` in this process.

    ``shot`` is a :class:`~flowreel.scene.shot.Shot` or a shot file path; ``source``
    defaults to the shot's own (:func:`open_source`); ``views`` and ``tracks`` to the
    ``cameras.yml`` beside the shot file; ``size`` (``(width, height)``) to the shot's.
    ``backend`` is chosen as in :func:`render`, so a frame drawn here and the same frame
    drawn by a render are the same picture. Returns ``(height, width, 3)`` uint8.
    """
    scene = Scene.make(shot, source, views, tracks, size)
    with _environment(backend_mod.environment(backend_mod.choose(backend))):
        return scene.draw(frame)


@dataclass
class FrameResult:
    """One frame of a :func:`render`: its index, the file, ``status`` (``rendered``),
    the seconds it took and the peak memory of its process in bytes (0 in-process)."""

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
    """Threads per job when not given: a few, and no more than the cores allow."""
    return max(1, min(4, (os.cpu_count() or 1) // max(jobs, 1)))


def render(shot, frames: Iterable[int] | None = None, source=None, *, views=None,
           tracks=None, out: str | Path = "frames", jobs: int = 1,
           threads: int | None = None, backend: str = "auto", processes: bool = True,
           progress: Callable[[FrameResult], None] | None = None) -> RenderReport:
    """Render ``frames`` (default all) of ``shot`` to PNG files.

    Frames go to ``out/<shot name>/frame_00000.png``. ``jobs`` frames are drawn at a time,
    each in its own process (``processes=False`` draws them here, one by one, for
    debugging). ``threads`` caps the threads of each job (default
    :func:`default_threads`). ``backend`` is one of
    :data:`flowreel.scene.backend.BACKENDS`. ``source`` must pickle when
    ``processes`` is true. ``progress`` is called with each finished
    :class:`FrameResult`. Returns a :class:`RenderReport`.
    """
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    scene = Scene.make(shot, source, views, tracks)
    indices = _frames(frames, scene.plan.n_frames, scene.shot)
    folder = Path(out) / scene.shot.name
    folder.mkdir(parents=True, exist_ok=True)
    threads = threads or default_threads(jobs)
    chosen = backend_mod.choose(backend)
    report = RenderReport(folder, chosen)
    results: dict[int, FrameResult] = {}

    def done(result: FrameResult):
        results[result.index] = result
        if progress:
            progress(result)

    todo = list(indices)
    with _environment(backend_mod.environment(chosen, threads)):
        if not processes:
            for i in todo:
                done(_draw_to_file(scene, i, folder / FRAME_NAME.format(i)))
        elif todo:
            job = _Job(scene.shot, source, views, tracks)
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=min(jobs, len(todo)), mp_context=ctx,
                                     max_tasks_per_child=1) as pool:
                futures = [pool.submit(_worker, job, i, str(folder / FRAME_NAME.format(i)))
                           for i in todo]
                for fut in as_completed(futures):
                    done(fut.result())
    report.frames = [results[i] for i in indices]
    return report


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


def _worker(job: _Job, index: int, path: str) -> FrameResult:
    scene = Scene.make(job.shot, job.source, job.views, job.tracks)
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
