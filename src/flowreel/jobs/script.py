"""Job scripts (plan Section 19.6): a :class:`~flowreel.jobs.spec.JobSpec` written out
for ``sbatch``, as a person would write it.

The script runs FlowReel from the environment it was written from (its ``bin`` first
on the path, so the environment's ffmpeg is found too), with no display, in the folder
it was written for. It first checks off-screen drawing (``python -m
flowreel.jobs.check``), so a node without OpenGL fails in seconds rather than after
loading data. A job array runs each task's commands from a ``case`` on
``SLURM_ARRAY_TASK_ID``.

Slurm does not make the folder of the output file, and a job whose log cannot be
opened fails without a word, so :func:`write` makes it.
"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path

import flowreel
from flowreel.jobs.partitions import format_memory, format_time
from flowreel.jobs.spec import JobSpec


def _line(command) -> str:
    return command if isinstance(command, str) else shlex.join(str(c) for c in command)


def job_script(spec: JobSpec, commands=(), tasks=None, *, workdir: str | Path,
               environment: str | Path | None = None, check: bool = True,
               written_by: str | None = None) -> str:
    """The text of a job script for ``spec``.

    ``commands`` are run in order (each an argument list, or a line of shell); with
    ``tasks`` (one list of commands per array task, as many as ``spec.tasks``), task
    ``k`` runs ``tasks[k]`` after them. ``workdir`` is the folder the job runs in (its
    relative paths, the log's included, start there); ``environment`` the Python
    environment whose ``bin`` comes first on the path (default this one's). ``check``
    adds the off-screen check. ``written_by`` is the command that wrote it, for the
    header."""
    spec.check()
    if (tasks is None) != (spec.tasks is None):
        raise ValueError("give tasks for a job array (spec.tasks), and only then")
    if tasks is not None and len(tasks) != spec.tasks:
        raise ValueError(f"the array has {spec.tasks} tasks, but {len(tasks)} were given")
    env = Path(environment if environment is not None else sys.prefix)
    lines = ["#!/bin/bash",
             f"# Written by flowreel {flowreel.__version__}"
             + (f": {written_by}" if written_by else "") + ".",
             "# Submit with: sbatch THIS_FILE. Frames already drawn are skipped, so a job",
             "# that stopped can be submitted again as it is.",
             f"#SBATCH --job-name={spec.name}",
             f"#SBATCH --partition={spec.partition.name}",
             "#SBATCH --nodes=1",
             "#SBATCH --ntasks=1",
             f"#SBATCH --cpus-per-task={spec.cpus}"]
    if spec.memory is not None:
        lines.append(f"#SBATCH --mem={format_memory(spec.memory)}")
    lines.append(f"#SBATCH --time={format_time(spec.time)}")
    if spec.tasks is not None:
        cap = f"%{spec.max_running}" if spec.max_running else ""
        lines.append(f"#SBATCH --array=0-{spec.tasks - 1}{cap}")
    if spec.after:
        lines.append(f"#SBATCH --dependency=afterok:{':'.join(map(str, spec.after))}")
    lines += [f"#SBATCH --chdir={Path(workdir).resolve()}",
              f"#SBATCH --output={spec.log_pattern}",
              "",
              "set -euo pipefail",
              f"export PATH={shlex.quote(str(env / 'bin'))}:\"$PATH\"",
              "unset DISPLAY                 # drawn off-screen (EGL or OSMesa)",
              'echo "flowreel job ${SLURM_JOB_ID:-?}'
              + (" task ${SLURM_ARRAY_TASK_ID:-?}" if spec.tasks is not None else "")
              + ' on $(hostname): ${SLURM_CPUS_PER_TASK:-?} cores, started $(date)"']
    if check:
        lines.append("python -m flowreel.jobs.check")
    lines += [_line(c) for c in commands]
    if tasks is not None:
        lines.append('case "$SLURM_ARRAY_TASK_ID" in')
        for k, task in enumerate(tasks):
            body = [_line(c) for c in task] or [":"]
            if len(body) == 1:
                lines.append(f"  {k}) {body[0]} ;;")
            else:
                lines.append(f"  {k})")
                lines += [f"    {b}" for b in body]
                lines.append("    ;;")
        lines.append('  *) echo "no task $SLURM_ARRAY_TASK_ID" >&2; exit 2 ;;')
        lines.append("esac")
    lines.append('echo "done $(date)"')
    return "\n".join(lines) + "\n"


def write(path: str | Path, text: str, spec: JobSpec, workdir: str | Path) -> Path:
    """Write the script ``text`` of ``spec`` to ``path``, executable, and make the
    folder of its log under ``workdir``; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    log_dir = (Path(workdir) / spec.log_pattern).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    return path
