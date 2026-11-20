"""A Slurm job as FlowReel asks for it: one process tree on one node (plan Section 19.6).

A render is one job of ``cpus`` cores and ``memory`` bytes for ``time`` seconds, or a
job array of ``tasks`` such jobs, of which at most ``max_running`` run at once, so a
render can take part of a shared node. :meth:`JobSpec.check` holds it against its
partition (:mod:`flowreel.jobs.partitions`) and says which limit it breaks.
"""
from __future__ import annotations

from dataclasses import dataclass

from flowreel.jobs.partitions import Partition, format_memory, format_time


class JobError(ValueError):
    """A job its partition cannot take."""


@dataclass(frozen=True)
class JobSpec:
    """One job, or a job array.

    ``name`` names it in the queue; ``partition`` is where it runs; ``cpus`` the cores
    of one task, ``memory`` its bytes (``None``: the partition's default), ``time`` its
    seconds; ``tasks`` the array's size (``None``: a single job) and ``max_running`` how
    many of them run at once (``None``: as many as fit); ``after`` the job ids that must
    end well first (``afterok``); ``log`` the output file, in Slurm's patterns (``%x``
    the name, ``%j`` the job, ``%A`` and ``%a`` the array and the task)."""

    name: str
    partition: Partition
    cpus: int = 1
    memory: int | None = None
    time: int = 3600
    tasks: int | None = None
    max_running: int | None = None
    after: tuple[str, ...] = ()
    log: str | None = None

    @property
    def log_pattern(self) -> str:
        """The output file: ``log``, else ``logs/<name>_<job>.log`` (per task for an
        array)."""
        if self.log:
            return self.log
        return "logs/%x_%A_%a.log" if self.tasks is not None else "logs/%x_%j.log"

    def check(self) -> "JobSpec":
        """Raise :class:`JobError` when the partition cannot take this job; returns the
        job."""
        p = self.partition
        where = f"partition {p.name} of {p.cluster}"
        if not self.name or any(c.isspace() for c in self.name):
            raise JobError(f"a job's name is one word, got {self.name!r}")
        if self.cpus < 1:
            raise JobError(f"a job needs at least 1 core, got {self.cpus}")
        if p.job_cpus is not None and self.cpus > p.job_cpus:
            raise JobError(f"{where} gives a job at most {p.job_cpus} cores; asked {self.cpus}")
        if self.memory is not None:
            if self.memory <= 0:
                raise JobError(f"a job's memory must be positive, got {self.memory} bytes")
            if p.memory is not None and self.memory > p.memory:
                raise JobError(f"{where} has {format_memory(p.memory)} on a node; asked "
                               f"{format_memory(self.memory)}")
        if self.time <= 0:
            raise JobError(f"a job's time must be positive, got {self.time} s")
        if self.time > p.time:
            raise JobError(f"{where} runs a job for at most {format_time(p.time)}; asked "
                           f"{format_time(self.time)}")
        if not p.shared:
            raise JobError(f"{where} gives whole nodes to MPI jobs ({p.note or 'not shared'}); "
                           "a render is one process tree, so use a shared partition")
        if self.tasks is not None and self.tasks < 1:
            raise JobError(f"a job array needs at least 1 task, got {self.tasks}")
        if self.max_running is not None:
            if self.tasks is None:
                raise JobError("max_running is for a job array (tasks)")
            if self.max_running < 1:
                raise JobError(f"max_running must be at least 1, got {self.max_running}")
        for job in self.after:
            if not str(job).replace("_", "").isdigit():
                raise JobError(f"after: expected Slurm job ids such as 1301, got {job!r}")
        return self
