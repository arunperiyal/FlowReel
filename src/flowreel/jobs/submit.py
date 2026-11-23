"""Handing job scripts to Slurm, and what became of them (plan Section 19.6).

:func:`submit` runs ``sbatch --parsable`` and returns the job id. Each job FlowReel
submits is noted in ``.flowreel/jobs.json`` in the folder it runs in (:func:`note`), with
the frames it draws, so ``jobs status`` can say how far a render got. :func:`status`
asks ``squeue`` for jobs still queued or running and ``sacct`` for the rest.

``sbatch``, ``squeue`` and ``sacct`` are found on the path; ``FLOWREEL_SBATCH`` (and
``FLOWREEL_SQUEUE``, ``FLOWREEL_SACCT``) name other ones, as the tests' fakes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time as _time
from dataclasses import dataclass
from pathlib import Path

RECORD = Path(".flowreel") / "jobs.json"


class SlurmError(RuntimeError):
    """Slurm is missing here, or refused a job."""


def tool(name: str) -> str:
    """The path of Slurm's ``name`` (``sbatch``, ``squeue``, ``sacct``)."""
    found = os.environ.get(f"FLOWREEL_{name.upper()}") or shutil.which(name)
    if not found:
        raise SlurmError(f"{name} is not found: submit from a Slurm cluster's login node (the "
                         "script can be written anywhere with --slurm FILE and copied there)")
    return found


def submit(script: str | Path, workdir: str | Path | None = None) -> str:
    """Submit ``script`` with ``sbatch --parsable`` from ``workdir``; returns the job id."""
    done = subprocess.run([tool("sbatch"), "--parsable", str(script)], capture_output=True,
                          text=True, cwd=workdir)
    if done.returncode != 0:
        raise SlurmError(f"sbatch refused {script}: {(done.stderr or done.stdout).strip()}")
    job = done.stdout.strip().split(";")[0]
    if not job.isdigit():
        raise SlurmError(f"sbatch gave no job id for {script}: {done.stdout.strip()!r}")
    return job


def note(workdir: str | Path, job: str, name: str, kind: str, script: str | Path,
         folder: str | Path | None = None, frames: list[int] | None = None) -> None:
    """Add job ``job`` to the record of ``workdir``: its ``name``, ``kind`` (``render``,
    ``measure``, ``compose``, ``film``), ``script``, and for a render its frame
    ``folder`` and ``frames``."""
    path = Path(workdir) / RECORD
    entries = notes(workdir)
    entries.append({"job": str(job), "name": name, "kind": kind, "script": str(script),
                    "folder": None if folder is None else str(folder),
                    "frames": frames, "submitted": _time.time()})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"jobs.{os.getpid()}.part")
    tmp.write_text(json.dumps(entries, indent=1) + "\n")
    os.replace(tmp, path)


def notes(workdir: str | Path) -> list[dict]:
    """The jobs noted in ``workdir``, oldest first."""
    try:
        return json.loads((Path(workdir) / RECORD).read_text())
    except (OSError, ValueError):
        return []


@dataclass(frozen=True)
class JobState:
    """A job (or array task) as Slurm reports it: ``job`` id, ``name``, ``state``
    (``PENDING``, ``RUNNING``, ``COMPLETED``, ``FAILED``, ``TIMEOUT``, ``CANCELLED`` ...),
    ``elapsed`` time and ``reason`` (why pending, or the exit code)."""

    job: str
    name: str
    state: str
    elapsed: str
    reason: str = ""


def status(jobs: list[str]) -> list[JobState]:
    """Slurm's state of each of ``jobs`` and their array tasks: ``squeue`` for those
    queued or running, ``sacct`` for the rest (when it is there)."""
    if not jobs:
        return []
    ids = ",".join(jobs)
    out: dict[str, JobState] = {}
    done = subprocess.run([tool("squeue"), "-h", "-j", ids, "-o", "%i|%j|%T|%M|%r"],
                          capture_output=True, text=True)
    for line in done.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 5:
            out[parts[0]] = JobState(*parts)
    try:
        sacct = tool("sacct")
    except SlurmError:
        sacct = None
    if sacct:
        done = subprocess.run([sacct, "-n", "-P", "-X", "-j", ids,
                               "--format=JobID,JobName,State,Elapsed,ExitCode"],
                              capture_output=True, text=True)
        for line in done.stdout.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 5 and parts[0] not in out and "[" not in parts[0]:
                job, name, state, elapsed, code = parts
                out[job] = JobState(job, name, state.split()[0], elapsed, f"exit {code}")
    for key in [k for k in out if "_[" in k]:     # tasks still pending, as one record
        base = key.split("_")[0]
        tasks = _task_ids(key.split("_[", 1)[1].rstrip("]"))
        if tasks and all(f"{base}_{i}" in out for i in tasks):
            del out[key]                            # started meanwhile: listed one by one
    return sorted(out.values(), key=lambda s: [int(x) if x.isdigit() else 0
                                               for x in s.job.replace("_", ".").split(".")])


def _task_ids(spec: str) -> list[int]:
    """The array task ids of a Slurm task list such as ``0-9%4`` or ``0,3,5-7``
    (empty when it does not read as one)."""
    ids = []
    for part in spec.split("%")[0].split(","):
        low, _, high = part.partition("-")
        if not low.isdigit() or (high and not high.isdigit()):
            return []
        ids += range(int(low), int(high or low) + 1)
    return ids


def state_text(state: JobState) -> str:
    """One job's state in words: why it waits, how long it has run, or how it ended."""
    reason = "" if state.reason in ("", "None", "(null)") else state.reason
    if state.state == "PENDING":
        return f"PENDING ({reason})" if reason else "PENDING"
    if state.state == "RUNNING":
        return f"RUNNING for {state.elapsed}"
    return f"{state.state} after {state.elapsed}" + (f", {reason}" if reason else "")


def frames_done(folder: str | Path, frames: list[int], since: float) -> int:
    """How many of ``frames`` in ``folder`` were written after ``since`` (seconds since
    the epoch): the frames a render drew since it was submitted."""
    from flowreel.scene.rendering import FRAME_NAME
    count = 0
    for i in frames:
        try:
            if (Path(folder) / FRAME_NAME.format(i)).stat().st_mtime >= since:
                count += 1
        except OSError:
            pass
    return count
