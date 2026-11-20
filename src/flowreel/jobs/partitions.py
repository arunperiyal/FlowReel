"""Clusters and their partitions (plan Section 14): what a job may ask for.

FlowReel keeps its own table, ``partitions.yml`` beside this module, starting with
airavata (``part1`` 3 h, ``part2`` 24 h, ``part3`` 72 h on ``node1``: 128 cores, 125
GB) and Param Shakti. ``~/.flowreel/partitions.yml``, written the same way, adds
clusters or overrides partitions (:func:`load`).

The cluster is the one named (``--cluster``), else ``FLOWREEL_CLUSTER``, else the one
whose ``hosts`` match this machine's name (:func:`find`). Times are seconds and memory
bytes inside FlowReel; :func:`parse_time`, :func:`format_time`, :func:`parse_memory`
and :func:`format_memory` turn them into Slurm's forms and back.
"""
from __future__ import annotations

import fnmatch
import os
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.errors import Checker

TABLE = Path(__file__).with_name("partitions.yml")
USER_TABLE = Path("~/.flowreel/partitions.yml")
ENV = "FLOWREEL_CLUSTER"
PARTITION_KEYS = ("time", "cpus", "memory", "max_cpus", "shared", "note")
CLUSTER_KEYS = ("hosts", "partitions")


@dataclass(frozen=True)
class Partition:
    """A partition of ``cluster``: the longest ``time`` a job may run (seconds), the
    ``cpus`` and ``memory`` (bytes) of one node (``None`` when not known), the most
    cores one job may ask for (``max_cpus``), whether jobs ``shared`` a node, and a
    ``note``."""

    name: str
    cluster: str
    time: int
    cpus: int | None = None
    memory: int | None = None
    max_cpus: int | None = None
    shared: bool = True
    note: str = ""

    @property
    def job_cpus(self) -> int | None:
        """The most cores one job may ask for."""
        return self.max_cpus if self.max_cpus is not None else self.cpus


@dataclass
class Cluster:
    """A cluster: its ``name``, the ``hosts`` (shell patterns) that pick it, and its
    ``partitions`` by name, in the table's order."""

    name: str
    hosts: tuple[str, ...] = ()
    partitions: dict[str, Partition] = field(default_factory=dict)

    def partition(self, name: str) -> Partition:
        """The partition ``name``; ``KeyError`` naming the others otherwise."""
        try:
            return self.partitions[name]
        except KeyError:
            raise KeyError(f"cluster {self.name} has no partition {name!r} (partitions: "
                           f"{', '.join(self.partitions)})") from None

    def fitting(self, time: int, cpus: int = 1, memory: int | None = None) -> Partition:
        """The shortest shared partition a job of ``time`` seconds, ``cpus`` cores and
        ``memory`` bytes fits in (then the shortest of any kind); ``ValueError`` when
        none does."""
        def fits(p: Partition) -> bool:
            return (p.time >= time and (p.job_cpus is None or cpus <= p.job_cpus)
                    and (memory is None or p.memory is None or memory <= p.memory))
        found = sorted((p for p in self.partitions.values() if fits(p)),
                       key=lambda p: (not p.shared, p.time))
        if not found:
            raise ValueError(f"no partition of {self.name} takes {format_time(time)} with "
                             f"{cpus} cores" + (f" and {format_memory(memory)}" if memory else ""))
        return found[0]


# -- times and memory ------------------------------------------------------------------

_UNITS = {"s": 1, "m": 60, "min": 60, "h": 3600, "d": 86400}


def parse_time(value) -> int:
    """Seconds from a time: Slurm's forms (``MM``, ``MM:SS``, ``HH:MM:SS``, ``D-HH``,
    ``D-HH:MM``, ``D-HH:MM:SS``; a bare number is minutes, as in Slurm) or a number with
    a unit (``90m``, ``3h``, ``2d``, ``45s``)."""
    text = str(value).strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|m|min|h|d)", text)
    if m:
        return round(float(m.group(1)) * _UNITS[m.group(2)])
    m = re.fullmatch(r"(?:(\d+)-)?(\d+)(?::(\d+))?(?::(\d+))?", text)
    if not m:
        raise ValueError(f"not a time: {value!r} (such as 90m, 3h, 2d, 02:30:00 or 1-12:00:00)")
    days, a, b, c = (int(g) if g is not None else None for g in m.groups())
    if days is not None:                       # D-HH, D-HH:MM, D-HH:MM:SS
        return days * 86400 + a * 3600 + (b or 0) * 60 + (c or 0)
    if c is not None:                          # HH:MM:SS
        return a * 3600 + b * 60 + c
    if b is not None:                          # MM:SS
        return a * 60 + b
    return a * 60                              # MM


def format_time(seconds: int) -> str:
    """``seconds`` as Slurm writes a time: ``HH:MM:SS``, or ``D-HH:MM:SS`` from a day."""
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    m, s = divmod(rest, 60)
    return f"{days}-{h:02d}:{m:02d}:{s:02d}" if days else f"{h:02d}:{m:02d}:{s:02d}"


_MEM = {"": 1024 ** 2, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4}


def parse_memory(value) -> int:
    """Bytes from a memory size: ``32G``, ``500M``, ``125 GB``, ``1.5T``; a bare number
    is megabytes, as in Slurm."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kmgt]?)i?b?", str(value).strip().lower())
    if not m:
        raise ValueError(f"not a memory size: {value!r} (such as 32G or 500M)")
    return round(float(m.group(1)) * _MEM[m.group(2)])


def format_memory(nbytes: int) -> str:
    """``nbytes`` as Slurm's ``--mem`` takes it: whole gigabytes (``32G``) when exact,
    else megabytes rounded up (``1536M``)."""
    if nbytes % 1024 ** 3 == 0:
        return f"{nbytes // 1024 ** 3}G"
    return f"{-(-nbytes // 1024 ** 2)}M"


# -- the table -------------------------------------------------------------------------

def _partition(name: str, cluster: str, spec, check: Checker) -> Partition:
    spec = check.mapping(spec, PARTITION_KEYS, required=("time",))

    def number(key):
        v = spec.get(key)
        return None if v is None else check.at(key).integer(v, minimum=1)

    def size(key):
        v = spec.get(key)
        if v is None:
            return None
        try:
            return parse_memory(v)
        except ValueError as exc:
            raise check.at(key).error(str(exc)) from None
    try:
        time = parse_time(spec["time"])
    except ValueError as exc:
        raise check.at("time").error(str(exc)) from None
    shared = spec.get("shared", True)
    if not isinstance(shared, bool):
        raise check.at("shared").error(f"expected true or false, got {shared!r}")
    return Partition(name, cluster, time, number("cpus"), size("memory"), number("max_cpus"),
                     shared, str(spec.get("note") or ""))


def _named(value, check: Checker) -> dict:
    """A mapping keyed by names (clusters, partitions): any keys, each a string."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise check.error(f"expected a mapping of names, got {type(value).__name__}")
    for key in value:
        if not isinstance(key, str) or not key:
            raise check.error(f"expected names as keys, got {key!r}")
    return dict(value)


def parse(data, file: str | None = None, base: dict[str, Cluster] | None = None) -> dict[str, Cluster]:
    """Clusters from a parsed table (``data``), added to or overriding ``base``."""
    check = Checker(file)
    out = {name: Cluster(c.name, c.hosts, dict(c.partitions)) for name, c in (base or {}).items()}
    for name, spec in _named(data, check).items():
        at = check.at(name)
        spec = at.mapping(spec, CLUSTER_KEYS)
        cluster = out.setdefault(name, Cluster(name))
        if "hosts" in spec:
            cluster.hosts = tuple(at.at("hosts", k).string(h)
                                  for k, h in enumerate(at.at("hosts").sequence(spec["hosts"] or [])))
        for pname, pspec in _named(spec.get("partitions"), at.at("partitions")).items():
            cluster.partitions[pname] = _partition(pname, name, pspec, at.at("partitions", pname))
    return out


def load(user: Path | None = None) -> dict[str, Cluster]:
    """FlowReel's table, then the user's (default ``~/.flowreel/partitions.yml``, when
    it exists) on top."""
    from flowreel.yamlfile import read_yaml
    clusters = parse(read_yaml(TABLE), str(TABLE))
    user = Path(user if user is not None else USER_TABLE).expanduser()
    if user.is_file():
        clusters = parse(read_yaml(user), str(user), clusters)
    return clusters


def find(name: str | None = None, clusters: dict[str, Cluster] | None = None, *,
         environ=None, host: str | None = None) -> Cluster:
    """The cluster called ``name``, else ``FLOWREEL_CLUSTER``, else the one whose hosts
    match this machine's name; ``LookupError`` saying how to name one otherwise."""
    clusters = load() if clusters is None else clusters
    environ = os.environ if environ is None else environ
    name = name or environ.get(ENV)
    if name:
        if name not in clusters:
            raise LookupError(f"no cluster {name!r} (clusters: {', '.join(clusters)})")
        return clusters[name]
    host = host if host is not None else socket.gethostname()
    short = host.split(".")[0]
    for cluster in clusters.values():
        if any(fnmatch.fnmatch(short, p) or fnmatch.fnmatch(host, p) for p in cluster.hosts):
            return cluster
    raise LookupError(f"this machine ({host}) is not a known cluster; give --cluster NAME or "
                      f"set {ENV} (clusters: {', '.join(clusters)}), or add it to "
                      f"{USER_TABLE}")
