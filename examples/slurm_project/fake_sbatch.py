#!/usr/bin/env python3
"""A stand-in for Slurm's ``sbatch``, for trying FlowReel's jobs without a cluster.

Usage: fake_sbatch.py --parsable SCRIPT      (as FlowReel calls sbatch)

It reads the script's ``#SBATCH`` lines and runs it at once, here, with Slurm's
variables set: ``SLURM_JOB_ID``, ``SLURM_CPUS_PER_TASK``, ``SLURM_MEM_PER_NODE``, and
for an array each task in turn with ``SLURM_ARRAY_JOB_ID`` and ``SLURM_ARRAY_TASK_ID``.
Each task's output goes to the log the script names (``--output``, with ``%x``, ``%j``,
``%A`` and ``%a`` filled in), from the folder it names (``--chdir``). Then it prints the
job id, as ``sbatch --parsable`` does. A job submitted from inside a job (a measuring job
submitting the render) runs the same way, before the outer job goes on.

``FAKE_SBATCH_TASKS=0,2`` runs only those tasks of an array, as if the others were
cancelled: a render cut short. Job ids count up from 1001; the count is kept in
``FAKE_SBATCH_STATE`` (default ``~/.flowreel/fake_sbatch.json``). Dependencies are
ignored: jobs run in the order they are submitted. Not part of the package.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def options(script: Path) -> dict:
    """The ``#SBATCH --key=value`` lines of ``script``."""
    found = {}
    for line in script.read_text().splitlines():
        m = re.match(r"#SBATCH\s+--([\w-]+)(?:=(.*))?", line)
        if m:
            found[m.group(1)] = (m.group(2) or "").strip()
    return found


def next_id() -> int:
    state = Path(os.environ.get("FAKE_SBATCH_STATE", "~/.flowreel/fake_sbatch.json")).expanduser()
    state.parent.mkdir(parents=True, exist_ok=True)
    try:
        last = json.loads(state.read_text())["last"]
    except (OSError, ValueError, KeyError):
        last = 1000
    state.write_text(json.dumps({"last": last + 1}))
    return last + 1


def megabytes(text: str) -> str:
    m = re.fullmatch(r"(\d+)([KMGT]?)", text.upper())
    if not m:
        return ""
    return str(int(m.group(1)) * {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 ** 2, "": 1}[m.group(2)])


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--parsable"]
    if len(args) != 1:
        print("fake sbatch: give one script", file=sys.stderr)
        return 1
    script = Path(args[0]).resolve()
    opts = options(script)
    job = next_id()
    workdir = Path(opts.get("chdir") or os.getcwd())
    name = opts.get("job-name", script.stem)
    env = {**os.environ, "SLURM_JOB_ID": str(job), "SLURM_JOB_NAME": name,
           "SLURM_CPUS_PER_TASK": opts.get("cpus-per-task", "1"),
           "SLURM_SUBMIT_DIR": os.getcwd()}
    if opts.get("mem"):
        env["SLURM_MEM_PER_NODE"] = str(int(float(megabytes(opts["mem"]) or 0)))
    tasks = [None]
    if "array" in opts:
        first, last = re.match(r"(\d+)-(\d+)", opts["array"]).groups()
        tasks = list(range(int(first), int(last) + 1))
        only = os.environ.get("FAKE_SBATCH_TASKS")
        if only:
            tasks = [t for t in tasks if str(t) in only.split(",")]
    print(job)                                 # as --parsable: the id first
    sys.stdout.flush()
    for task in tasks:
        task_env = dict(env)
        if task is not None:
            task_env.update(SLURM_ARRAY_JOB_ID=str(job), SLURM_ARRAY_TASK_ID=str(task))
        log = (opts.get("output") or "slurm-%j.out").replace("%x", name).replace(
            "%A", str(job)).replace("%a", str(task)).replace("%j", task_env["SLURM_JOB_ID"])
        log = workdir / log
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "w") as out:
            subprocess.run(["bash", str(script)], cwd=workdir, env=task_env, stdout=out,
                           stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
