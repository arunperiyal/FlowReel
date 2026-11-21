"""Cores and memory the running process may use (plan Sections 17 and 19.6).

A render sizes its jobs and threads from these numbers. In a Slurm job they are the
job's allocation, not the node's: a job given 16 of node1's 128 cores and 32 GB must
not start 128 jobs because the node is mostly idle. So, in a Slurm job (``SLURM_JOB_ID``
set):

* cores: the CPU affinity of this process, capped by ``SLURM_CPUS_PER_TASK`` (else
  ``SLURM_CPUS_ON_NODE``);
* memory: the smallest of ``SLURM_MEM_PER_NODE`` (MB), ``SLURM_MEM_PER_CPU`` (MB) times
  the cores, the room left under the cgroup's limit, and the machine's ``MemAvailable``.

Elsewhere: the CPU affinity (else ``os.cpu_count()``) and the smallest of
``MemAvailable`` and the room under a cgroup limit (a container's, say). The cgroup is
read from ``/proc/self/cgroup``, and every level from the process's own cgroup up to
the root counts, for both cgroup v2 (``memory.max`` minus ``memory.current``) and v1
(``memory.limit_in_bytes`` minus ``memory.usage_in_bytes``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

GB = 1024 ** 3
MB = 1024 ** 2
_NO_LIMIT = 2 ** 60          # cgroup v1 writes a huge number for "no limit"


@dataclass(frozen=True)
class Resources:
    """Cores and memory for this process, and where each number came from.

    ``cores`` is a count of CPUs, ``memory_bytes`` the memory free to use in bytes.
    ``cores_from`` and ``memory_from`` name the source of each (for example
    ``SLURM_CPUS_PER_TASK``, ``CPU affinity``, ``cgroup memory.max``,
    ``MemAvailable``). ``job`` is the Slurm job id (``1301``, or ``1301_4`` for an
    array task), ``None`` outside Slurm.
    """

    cores: int
    memory_bytes: int
    cores_from: str
    memory_from: str
    job: str | None = None

    @property
    def where(self) -> str:
        """``Slurm job 1301`` or ``this machine``."""
        return f"Slurm job {self.job}" if self.job else "this machine"

    def text(self) -> str:
        """One line for a report, e.g. ``Slurm job 1301: 16 cores, 32.0 GB (...)``."""
        return (f"{self.where}: {self.cores} cores, {self.memory_bytes / GB:.1f} GB "
                f"(cores from {self.cores_from}, memory from {self.memory_from})")


def resources(environ: Mapping[str, str] | None = None, *,
              meminfo: str | Path = "/proc/meminfo",
              proc_cgroup: str | Path = "/proc/self/cgroup",
              cgroup_root: str | Path = "/sys/fs/cgroup",
              affinity: int | None = None) -> Resources:
    """The cores and memory this process may use (see the module's notes).

    ``environ`` defaults to ``os.environ``; ``meminfo``, ``proc_cgroup`` and
    ``cgroup_root`` are the files read, and ``affinity`` the number of CPUs this
    process may run on (default from ``os.sched_getaffinity``). All are for tests.
    """
    env = os.environ if environ is None else environ
    job = _job_id(env)
    cores, cores_from = _cores(env if job else {}, affinity)

    memory = []                       # (bytes, where from); the smallest wins
    free = _mem_available(Path(meminfo))
    if free is not None:
        memory.append((free, "MemAvailable"))
    if job:
        if _positive_int(env.get("SLURM_MEM_PER_NODE")):
            memory.append((int(env["SLURM_MEM_PER_NODE"]) * MB, "SLURM_MEM_PER_NODE"))
        elif _positive_int(env.get("SLURM_MEM_PER_CPU")):
            memory.append((int(env["SLURM_MEM_PER_CPU"]) * MB * cores, "SLURM_MEM_PER_CPU"))
    limit = cgroup_room(proc_cgroup, cgroup_root)
    if limit is not None:
        memory.append(limit)
    if not memory:
        memory.append((os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES"),
                       "free pages"))
    bytes_, memory_from = min(memory, key=lambda m: m[0])
    return Resources(cores, max(int(bytes_), 0), cores_from, memory_from, job)


def cgroup_room(proc_cgroup: str | Path = "/proc/self/cgroup",
                cgroup_root: str | Path = "/sys/fs/cgroup") -> tuple[int, str] | None:
    """Bytes left under the tightest cgroup memory limit of this process, with the file
    that set it (``cgroup memory.max`` or ``cgroup memory.limit_in_bytes``); ``None``
    when no level of its cgroup has a limit."""
    try:
        lines = Path(proc_cgroup).read_text().splitlines()
    except OSError:
        return None
    root = Path(cgroup_root)
    rooms = []
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        _, controllers, path = parts
        if controllers == "":                                     # cgroup v2
            rooms += _rooms(root, path, "memory.max", "memory.current")
        elif "memory" in controllers.split(","):                  # cgroup v1
            rooms += _rooms(root / "memory", path, "memory.limit_in_bytes",
                            "memory.usage_in_bytes")
    return min(rooms, key=lambda r: r[0]) if rooms else None


def _rooms(base: Path, path: str, limit_name: str, usage_name: str) -> list[tuple[int, str]]:
    """Limit minus usage at every level from ``base/path`` up to ``base``."""
    rooms = []
    folder = base / path.strip("/")
    while True:
        limit = _read_int(folder / limit_name)
        if limit is not None and limit < _NO_LIMIT:
            usage = _read_int(folder / usage_name) or 0
            rooms.append((max(limit - usage, 0), f"cgroup {limit_name}"))
        if folder == base or base not in folder.parents:
            return rooms
        folder = folder.parent


def _read_int(path: Path) -> int | None:
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None        # "max": no limit


def _job_id(env: Mapping[str, str]) -> str | None:
    if not env.get("SLURM_JOB_ID"):
        return None
    array, task = env.get("SLURM_ARRAY_JOB_ID"), env.get("SLURM_ARRAY_TASK_ID")
    return f"{array}_{task}" if array and task else env["SLURM_JOB_ID"]


def _cores(env: Mapping[str, str], affinity: int | None) -> tuple[int, str]:
    if affinity is None:
        try:
            affinity = len(os.sched_getaffinity(0))
        except (AttributeError, OSError):
            affinity = None
    cores, where = (affinity, "CPU affinity") if affinity else (os.cpu_count() or 1,
                                                                "os.cpu_count")
    for name in ("SLURM_CPUS_PER_TASK", "SLURM_CPUS_ON_NODE"):
        if _positive_int(env.get(name)):
            if int(env[name]) < cores:
                cores, where = int(env[name]), name
            break
    return cores, where


def _positive_int(value: str | None) -> bool:
    return bool(value) and value.isdigit() and int(value) > 0


def _mem_available(meminfo: Path) -> int | None:
    try:
        with open(meminfo) as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None
