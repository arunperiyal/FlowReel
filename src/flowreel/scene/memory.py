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
import os
import time as _time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

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
    ``available_bytes`` the memory free on this machine, ``cpus`` its cores, ``threads``
    the threads the measured frame used, and ``jobs`` the suggested ``-j``
    (:func:`safe_jobs`).
    """

    frame: int
    peak_bytes: int
    seconds: float
    estimate_bytes: int | None
    available_bytes: int
    cpus: int
    threads: int
    jobs: int

    def text(self) -> str:
        """A short report for the terminal."""
        lines = [f"frame {self.frame}: peak {self.peak_bytes / GB:.2f} GB in {self.seconds:.1f} s"]
        if self.estimate_bytes is not None:
            lines.append(f"source estimate for one step: {self.estimate_bytes / GB:.2f} GB")
        lines.append(f"free memory {self.available_bytes / GB:.1f} GB, {self.cpus} cores; "
                     f"measured with {self.threads} threads")
        lines.append(f"suggested jobs: -j {self.jobs}")
        return "\n".join(lines)


def available_memory() -> int:
    """Memory free for new processes, in bytes (``MemAvailable`` on Linux)."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")


def safe_jobs(peak_bytes: int, available_bytes: int, cpus: int, threads: int = 1,
              headroom: float = HEADROOM) -> int:
    """How many jobs fit: as many frames of ``peak_bytes`` as ``headroom`` of the free
    memory holds, and no more than ``cpus // threads``; at least 1."""
    by_memory = math.floor(available_bytes * headroom / max(peak_bytes, 1))
    by_cores = max(cpus // max(threads, 1), 1)
    return max(1, min(by_memory, by_cores))


def measure(shot, frame: int = 0, source=None, *, views=None, tracks=None,
            scale: float | None = None, size: tuple[int, int] | None = None,
            threads: int | None = None, backend: str = "auto") -> MemoryReport:
    """Draw ``frame`` of ``shot`` in a fresh process and report its memory.

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
    estimate = None if estimate is None else int(estimate(shot.crop) * GB)
    env = backend_mod.environment(backend_mod.choose(backend), threads)
    with _environment(env), ProcessPoolExecutor(
            1, mp_context=multiprocessing.get_context("spawn")) as pool:
        peak, seconds = pool.submit(_measure_worker, _Job(shot, source, views, tracks, size),
                                    frame).result()
    cpus = os.cpu_count() or 1
    free = available_memory()
    return MemoryReport(frame, peak, seconds, estimate, free, cpus, threads,
                        safe_jobs(peak, free, cpus, cap_threads))


def _measure_worker(job: _Job, index: int) -> tuple[int, float]:
    start = _time.perf_counter()
    Scene.make(job.shot, job.source, job.views, job.tracks, job.size).draw(index)
    return peak_memory(), _time.perf_counter() - start
