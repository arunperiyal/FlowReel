"""Memory of one frame, and how many frames can be drawn at once (plan Section 17).

Memory, not cores, limits ``jobs``: a frame of the reference film takes about 0.7 GB
(bare) to 2.2 GB (helical), so 48 jobs of the larger kind would need 106 GB. The
measure is taken, not estimated: one frame is drawn in a fresh process, the same way
:func:`~flowreel.scene.rendering.render` draws it, and that process's peak resident
memory is read. The peak includes Python, VTK and the reader, which every job pays.
"""
from __future__ import annotations

import math
import multiprocessing
import time as _time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from flowreel.jobs.resources import resources
from flowreel.scene import backend as backend_mod
from flowreel.scene.rendering import (Scene, _as_shot, _environment, _Job, default_threads,
                                      draft_size, peak_memory)

GB = 1024 ** 3
HEADROOM = 0.8      # use at most this share of the free memory


@dataclass
class MemoryReport:
    """One measured frame and the jobs it allows.

    ``peak_bytes`` is the peak of the process that drew frame ``frame``, ``seconds``
    the time it took (opening the source included), ``estimate_bytes`` the source's own
    estimate for one step (``Source.memory_per_step``; ``None`` if it gives none),
    ``available_bytes`` the memory free to use, ``cpus`` the cores (both of the Slurm job
    when run in one, :func:`flowreel.jobs.resources.resources`), ``threads`` the threads
    the measured frame used, ``jobs`` the suggested ``-j`` (:func:`safe_jobs`), and
    ``where`` where the memory and cores came from (``this machine, MemAvailable``).
    """

    frame: int
    peak_bytes: int
    seconds: float
    estimate_bytes: int | None
    available_bytes: int
    cpus: int
    threads: int
    jobs: int
    where: str = "this machine"

    def text(self) -> str:
        """A short report for the terminal."""
        lines = [f"frame {self.frame}: peak {self.peak_bytes / GB:.2f} GB in {self.seconds:.1f} s"]
        if self.estimate_bytes is not None:
            lines.append(f"source estimate for one step: {self.estimate_bytes / GB:.2f} GB")
        lines.append(f"free memory {self.available_bytes / GB:.1f} GB, {self.cpus} cores "
                     f"({self.where}); "
                     f"measured with {self.threads} threads")
        lines.append(f"suggested jobs: -j {self.jobs}")
        return "\n".join(lines)


def available_memory() -> int:
    """Memory free for new processes, in bytes: ``MemAvailable``, or less under a Slurm
    job's or a cgroup's limit (:func:`flowreel.jobs.resources.resources`)."""
    return resources().memory_bytes


#: Memory of a render job before any data: Python, VTK and the reader (measured).
BASE_BYTES = int(0.7 * GB)


class NotEnoughMemory(ValueError):
    """A render that cannot fit in this machine's free memory."""


def estimate_job(scene, frames=None, samples: int = 5) -> int | None:
    """Bytes one render job is expected to need: :data:`BASE_BYTES` plus the source's
    own estimate (``memory_per_step``) for the frame that reads the most, among a few
    of ``frames`` (all frames by default) when the crop travels. ``None`` when the
    source gives no estimate."""
    estimate = getattr(scene.source, "memory_per_step", None)
    if estimate is None:
        return None
    frames = list(range(scene.plan.n_frames)) if frames is None else list(frames)
    if not frames:
        return None
    from flowreel.scene.shot import CropAround
    if isinstance(scene.shot.crop, CropAround) and len(frames) > samples:
        picks = np.linspace(0, len(frames) - 1, samples).round().astype(int)
        frames = [frames[i] for i in picks]
    elif not isinstance(scene.shot.crop, CropAround):
        frames = frames[:1]                       # one box for every frame
    return BASE_BYTES + int(max(estimate(scene.crop(i)) for i in frames) * GB)


def check_fits(scene, frames, jobs: int, available: int | None = None,
               headroom: float = HEADROOM, measured: int | None = None) -> int | None:
    """Raise :class:`NotEnoughMemory` when ``jobs`` jobs do not fit in ``headroom`` of
    the ``available`` memory (default :func:`available_memory`), saying what does. A job
    needs ``measured`` bytes, the peak measured for these frames, when given (a Slurm
    job is sized from it, so it must be checked by it too), else :func:`estimate_job`.
    Returns the bytes per job (``None``: no estimate, no check)."""
    per_job = measured or estimate_job(scene, frames)
    if per_job is None:
        return None
    available = available_memory() if available is None else available
    room = available * headroom
    if per_job > room:
        raise NotEnoughMemory(
            f"one frame needs about {per_job / GB:.1f} GB ({BASE_BYTES / GB:.1f} GB for "
            f"Python and VTK, the rest for the data) and {room / GB:.1f} GB is free to use; "
            "read less (crop the shot, or crop: {around: ...} for a long body) or render "
            "on a machine with more memory")
    fits = int(room // per_job)
    if jobs > fits:
        raise NotEnoughMemory(
            f"-j {jobs} needs about {jobs * per_job / GB:.1f} GB ({per_job / GB:.1f} GB per "
            f"job) and {room / GB:.1f} GB is free to use: use -j {fits} or fewer")
    return per_job


def safe_jobs(peak_bytes: int, available_bytes: int, cpus: int, threads: int = 1,
              headroom: float = HEADROOM) -> int:
    """How many jobs fit: as many frames of ``peak_bytes`` as ``headroom`` of the free
    memory holds, and no more than ``cpus // threads``; at least 1."""
    by_memory = math.floor(available_bytes * headroom / max(peak_bytes, 1))
    by_cores = max(cpus // max(threads, 1), 1)
    return max(1, min(by_memory, by_cores))


def measure(shot, frame: int = 0, source=None, *, views=None, tracks=None,
            scale: float | None = None, size: tuple[int, int] | None = None,
            threads: int | None = None, backend: str = "auto",
            out: str | None = None) -> MemoryReport:
    """Draw ``frame`` of ``shot`` in a fresh process and report its memory.

    With ``out`` (the folder of the frame folders, as for ``render``), the result is
    also kept beside the shot's frames (:mod:`flowreel.jobs.measured`), so a job array
    is sized from it.

    The options are those of :func:`~flowreel.scene.rendering.render`. Frame 0 is the
    default: in a frozen shot it is the one that contours. The picture is not saved.
    The suggested jobs are capped by the cores at ``threads`` per job when ``threads``
    is given, else at one per core, since a render lowers its threads per job as
    ``jobs`` grows (:func:`~flowreel.scene.rendering.default_threads`).
    """
    cap_threads = threads or 1
    shot = _as_shot(shot)
    size = draft_size(shot.size, scale, size)
    scene = Scene.make(shot, source, views, tracks, size)   # checks the shot and frame here
    if not 0 <= frame < scene.plan.n_frames:
        raise IndexError(f"frame {frame} is outside 0..{scene.plan.n_frames - 1}")
    threads = threads or default_threads(1)
    estimate = getattr(scene.source, "memory_per_step", None)
    estimate = None if estimate is None else int(estimate(scene.crop(frame)) * GB)
    env = backend_mod.environment(backend_mod.choose(backend), threads)
    with _environment(env), ProcessPoolExecutor(
            1, mp_context=multiprocessing.get_context("spawn")) as pool:
        peak, seconds = pool.submit(_measure_worker, _Job(shot, source, views, tracks, size),
                                    frame).result()
    have = resources()
    if out is not None:
        from flowreel.jobs import measured
        from flowreel.scene.rendering import frame_folder
        measured.save(frame_folder(out, shot, size),
                      measured.from_frames([peak], [seconds], threads))
    return MemoryReport(frame, peak, seconds, estimate, have.memory_bytes, have.cores,
                        threads, safe_jobs(peak, have.memory_bytes, have.cores, cap_threads),
                        f"{have.where}, {have.memory_from}")


def _measure_worker(job: _Job, index: int) -> tuple[int, float]:
    start = _time.perf_counter()
    Scene.make(job.shot, job.source, job.views, job.tracks, job.size).draw(index)
    return peak_memory(), _time.perf_counter() - start
