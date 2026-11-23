"""A render split into the tasks of a job array (plan Section 19.6).

:func:`plan_render` takes the frames to draw and what one frame costs
(:class:`~flowreel.jobs.measured.Measured`), and decides, within a partition:

- **per task:** ``cpus`` cores and ``memory``; ``jobs`` frames drawn at once
  (``flowreel shot render -j``) at ``threads`` threads each. Jobs are as many as the
  cores take at ``threads`` each, and no more than the memory holds (each needs the
  measured peak, with :data:`HEADROOM`). Memory left out is asked for to fit those jobs
  and the render's own process (:data:`PARENT`), rounded up to a whole GB.
- **tasks:** consecutive runs of frames, about :data:`ROUNDS` frames per job each, so a
  task loads Python and VTK once for many frames, and a task cut short loses little.
  At most ``max_running`` tasks run at once, so a render takes part of a shared node.
- **time:** the measured seconds a frame, times the rounds, with :data:`MARGIN` and
  :data:`START` added, unless given; a task that would outrun the longest partition is
  cut into smaller ones.

A render cut short is submitted again as it is: frames drawn with their key are skipped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from flowreel.jobs.measured import Measured
from flowreel.jobs.partitions import Cluster, Partition, format_memory, format_time

GB = 1024 ** 3
HEADROOM = 0.8        # jobs use at most this share of a task's memory
#: The render's own process (Python, VTK and the scene), which runs beside its jobs and
#: whose memory the render's check (flowreel.scene.memory.check_fits) finds in use.
PARENT = int(0.7 * GB)
ROUNDS = 8            # frames per job in a task
MARGIN = 1.5          # time asked for, over the measured time
START = 600           # seconds a task needs besides drawing (start, imports, opening data)
CPUS = 16             # cores of a task, when not given


class NeedMeasure(ValueError):
    """No measurement of the shot's frames yet; run ``shot memory`` (or a render) first."""


@dataclass(frozen=True)
class RenderPlan:
    """A render planned: ``runs`` of frames (each a list, consecutive in the frames
    asked for), one per task; per task ``cpus``, ``memory`` (bytes), ``jobs`` and
    ``threads``; the ``time`` of a task (seconds) and its ``partition``; at most
    ``max_running`` tasks at once (``None``: as Slurm schedules); the ``estimate`` of a
    task's drawing time (seconds), from ``measured``; and ``notes`` to print."""

    runs: list[list[int]]
    cpus: int
    memory: int
    jobs: int
    threads: int
    time: int
    partition: Partition
    max_running: int | None
    estimate: float
    measured: Measured
    notes: list[str] = field(default_factory=list)

    @property
    def tasks(self) -> int:
        """The number of tasks."""
        return len(self.runs)

    def text(self) -> str:
        """The plan in a few lines, for the terminal."""
        n = sum(len(r) for r in self.runs)
        lines = [f"{n} frames in {self.tasks} task{'s' * (self.tasks != 1)} of up to "
                 f"{max(len(r) for r in self.runs)} frames"
                 + (f", {self.max_running} at once" if self.max_running else ""),
                 f"each task: {self.cpus} cores, {format_memory(self.memory)}, -j {self.jobs} "
                 f"--threads {self.threads}, {format_time(self.time)} on "
                 f"{self.partition.cluster} {self.partition.name} (drawing about "
                 f"{format_time(round(self.estimate))})",
                 f"one frame: {self.measured.text()}"]
        return "\n".join(lines + self.notes)


def frames_spec(frames: list[int]) -> str:
    """``frames`` written for ``--frames``: ``A:B`` for each consecutive run, joined by
    commas (``0:9,12,20:24``)."""
    out, start = [], None
    for k, f in enumerate(frames):
        if start is None:
            start = f
        if k + 1 == len(frames) or frames[k + 1] != f + 1:
            out.append(str(f) if f == start else f"{start}:{f}")
            start = None
    return ",".join(out)


def _ceil_gb(nbytes: float) -> int:
    return math.ceil(nbytes / GB) * GB


def plan_render(frames: list[int], measured: Measured | None, cluster: Cluster, *,
                partition: str | None = None, cpus: int | None = None,
                memory: int | None = None, time: int | None = None, threads: int = 1,
                max_running: int | None = None, rounds: int = ROUNDS) -> RenderPlan:
    """Plan the render of ``frames`` (see the module) on ``cluster``, in ``partition``
    (default: the shortest that takes a task). ``cpus``, ``memory`` (bytes) and
    ``time`` (seconds) per task are worked out when left out. Raises
    :class:`NeedMeasure` without ``measured``, and ``ValueError`` when a frame does not
    fit the memory asked for or no partition takes a task."""
    if measured is None:
        raise NeedMeasure("no measurement of this shot's frames yet: run `flowreel shot "
                          "memory SHOT -o OUT` (or render a few frames) first")
    frames = sorted(set(frames))
    if not frames:
        raise ValueError("no frames to draw")
    if threads < 1:
        raise ValueError(f"threads must be at least 1, got {threads}")
    fixed = cluster.partition(partition) if partition else None
    widest = max((p.job_cpus or CPUS for p in ([fixed] if fixed else cluster.partitions.values())
                  if p.shared), default=CPUS)
    cpus = cpus or min(CPUS, widest)
    need = measured.peak_bytes / HEADROOM          # memory one job needs
    if memory is not None and memory < need + PARENT:
        raise ValueError(f"one frame needs about {format_memory(_ceil_gb(need + PARENT))} "
                         f"(peak {measured.peak_bytes / GB:.2f} GB, used to {HEADROOM:.0%}, "
                         f"and {PARENT / GB:.1f} GB for the render itself); asked "
                         f"{format_memory(memory)} a task")
    jobs = max(1, min(cpus // threads, len(frames),
                      math.floor((memory - PARENT) / need) if memory is not None else cpus))
    cap = fixed.memory if fixed and fixed.memory else max(
        (p.memory for p in cluster.partitions.values() if p.shared and p.memory), default=None)
    if memory is None:
        memory = _ceil_gb(need * jobs + PARENT)
        if cap is not None and memory > cap:           # fewer jobs on a smaller node
            jobs = max(1, math.floor((cap - PARENT) / need))
            memory = _ceil_gb(need * jobs + PARENT)
            if memory > cap:
                raise ValueError(f"one frame needs about {format_memory(_ceil_gb(need + PARENT))}, "
                                 f"more than a node of {cluster.name} has")
    seconds = measured.seconds * measured.threads / threads     # threads speed drawing
    longest = (fixed or max((p for p in cluster.partitions.values() if p.shared),
                            key=lambda p: p.time)).time
    per_task = jobs * rounds
    while True:
        task_rounds = math.ceil(min(per_task, len(frames)) / jobs)
        estimate = task_rounds * seconds
        need_time = time or round(estimate * MARGIN + START)
        if need_time <= longest or per_task <= jobs:
            break
        per_task = max(jobs, per_task // 2)
    notes = []
    if time is not None and estimate + START > time:
        notes.append(f"warning: a task may need {format_time(round(estimate + START))}, more "
                     f"than the {format_time(time)} asked for; it would stop part way, and "
                     "the render can then be submitted again")
    if need_time > longest:
        raise ValueError(f"one round of {jobs} frames takes about {format_time(round(seconds))}"
                         f", longer than {cluster.name}'s longest partition allows")
    part = fixed or cluster.fitting(need_time, cpus, memory)
    runs = [frames[k:k + per_task] for k in range(0, len(frames), per_task)]
    if max_running is not None and max_running < 1:
        raise ValueError(f"max_running must be at least 1, got {max_running}")
    return RenderPlan(runs, cpus, memory, jobs, threads, need_time, part,
                      min(max_running, len(runs)) if max_running else None, estimate,
                      measured, notes)


def render_commands(plan: RenderPlan, shot: str, *, out: str = "frames",
                    scale: float | None = None, size: tuple[int, int] | None = None,
                    backend: str = "auto") -> list[list[list[str]]]:
    """The commands of each task of ``plan``: one ``flowreel shot render`` of its
    frames, with the plan's ``-j`` and ``--threads``."""
    extra = []
    if scale is not None:
        extra += ["--scale", f"{scale:g}"]
    if size is not None:
        extra += ["--size", str(size[0]), str(size[1])]
    if backend != "auto":
        extra += ["--backend", backend]
    return [[["flowreel", "shot", "render", str(shot), "--frames", frames_spec(run),
              "-j", str(plan.jobs), "--threads", str(plan.threads), "-o", str(out), *extra]]
            for run in plan.runs]


def render_job(plan: RenderPlan, name: str, *, after=(), log: str | None = None):
    """The :class:`~flowreel.jobs.spec.JobSpec` of ``plan``: a job array named
    ``name``, one task per run, waiting for the jobs ``after``."""
    from flowreel.jobs.spec import JobSpec
    return JobSpec(name, plan.partition, cpus=plan.cpus, memory=plan.memory, time=plan.time,
                   tasks=plan.tasks, max_running=plan.max_running,
                   after=tuple(str(a) for a in after), log=log).check()


#: The measuring job: a few cores, memory for one frame of a large case (AFMS's
#: helical frames take 2.2 GB), time to open the data and draw it. A shared node keeps
#: the rest; ``memory`` asks for more.
MEASURE_CPUS, MEASURE_MEMORY, MEASURE_TIME = 4, 16 * GB, 1800


def measure_job(cluster: Cluster, name: str, shot: str, then, *, out: str = "frames",
                frame: int = 0, memory: int | None = None, scale: float | None = None,
                size: tuple[int, int] | None = None, backend: str = "auto", after=()):
    """A first job for a shot with no measurement yet: it draws ``frame`` with
    ``flowreel shot memory ... -o OUT``, which keeps the result beside the frames, then
    runs ``then`` (the command that plans and submits the render, now that it can be
    sized). ``memory`` defaults to :data:`MEASURE_MEMORY`. Returns ``(JobSpec,
    commands)``."""
    from flowreel.jobs.spec import JobSpec
    memory = MEASURE_MEMORY if memory is None else memory
    part = cluster.fitting(MEASURE_TIME, MEASURE_CPUS, memory)
    extra = []
    if scale is not None:
        extra += ["--scale", f"{scale:g}"]
    if size is not None:
        extra += ["--size", str(size[0]), str(size[1])]
    if backend != "auto":
        extra += ["--backend", backend]
    commands = [["flowreel", "shot", "memory", str(shot), "--frame", str(frame), "-o", str(out),
                 *extra], list(then)]
    spec = JobSpec(f"{name}_measure", part, cpus=MEASURE_CPUS, memory=memory,
                   time=MEASURE_TIME, after=tuple(str(a) for a in after)).check()
    return spec, commands
