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
