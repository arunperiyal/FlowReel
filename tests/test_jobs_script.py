"""jobs.script: job scripts, exact text."""
import subprocess

import pytest

import flowreel
from flowreel.jobs import partitions as p
from flowreel.jobs.script import job_script, write
from flowreel.jobs.spec import JobError, JobSpec

GB = 1024 ** 3
PART1 = p.load(user=p.Path("/nonexistent.yml"))["airavata"].partition("part1")
V = flowreel.__version__


def test_a_single_job(tmp_path):
    spec = JobSpec("reveal", PART1, cpus=16, memory=32 * GB, time=7200)
    text = job_script(spec, [["flowreel", "shot", "render", "reveal.yml", "-j", "8"]],
                      workdir=tmp_path, environment="/env", written_by="flowreel shot render "
                      "reveal.yml --slurm render.sh")
    assert text == f"""#!/bin/bash
# Written by flowreel {V}: flowreel shot render reveal.yml --slurm render.sh.
# Submit with: sbatch THIS_FILE. Frames already drawn are skipped, so a job
# that stopped can be submitted again as it is.
#SBATCH --job-name=reveal
#SBATCH --partition=part1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --chdir={tmp_path.resolve()}
#SBATCH --output=logs/%x_%j.log

set -euo pipefail
export PATH=/env/bin:"$PATH"
unset DISPLAY                 # drawn off-screen (EGL or OSMesa)
echo "flowreel job ${{SLURM_JOB_ID:-?}} on $(hostname): ${{SLURM_CPUS_PER_TASK:-?}} cores, started $(date)"
python -m flowreel.jobs.check
flowreel shot render reveal.yml -j 8
echo "done $(date)"
"""


def test_an_array_after_other_jobs(tmp_path):
    spec = JobSpec("wake", PART1, cpus=8, time=3600, tasks=3, max_running=2,
                   after=("1301", "1302"))
    text = job_script(spec, tasks=[[["flowreel", "shot", "render", "my shot.yml", "--frames", "0:9"]],
                                   [["echo", "a"], ["echo", "b"]], []],
                      workdir=tmp_path, environment="/my env", check=False)
    assert "#SBATCH --mem" not in text
    assert "#SBATCH --array=0-2%2\n#SBATCH --dependency=afterok:1301:1302\n" in text
    assert "#SBATCH --output=logs/%x_%A_%a.log" in text
    assert "export PATH='/my env/bin':\"$PATH\"" in text and "jobs.check" not in text
    assert "task ${SLURM_ARRAY_TASK_ID:-?} on" in text
    assert text.endswith("""case "$SLURM_ARRAY_TASK_ID" in
  0) flowreel shot render 'my shot.yml' --frames 0:9 ;;
  1)
    echo a
    echo b
    ;;
  2) : ;;
  *) echo "no task $SLURM_ARRAY_TASK_ID" >&2; exit 2 ;;
esac
echo "done $(date)"
""")


def test_tasks_must_match_the_array(tmp_path):
    with pytest.raises(ValueError, match="3 tasks, but 2"):
        job_script(JobSpec("w", PART1, tasks=3), tasks=[[], []], workdir=tmp_path)
    with pytest.raises(ValueError, match="only then"):
        job_script(JobSpec("w", PART1), tasks=[[]], workdir=tmp_path)
    with pytest.raises(JobError, match="at most 03:00:00"):
        job_script(JobSpec("w", PART1, time=5 * 3600), workdir=tmp_path)


def test_write_makes_the_log_folder_and_the_script_runs(tmp_path):
    spec = JobSpec("probe", PART1, tasks=2)
    text = job_script(spec, tasks=[[["echo", "first"]], [["echo", "second"]]],
                      workdir=tmp_path, check=False)
    path = write(tmp_path / "jobs" / "probe.sh", text, spec, tmp_path)
    assert (tmp_path / "logs").is_dir() and path.stat().st_mode & 0o111
    done = subprocess.run(["bash", str(path)], capture_output=True, text=True,
                          env={"SLURM_ARRAY_TASK_ID": "1", "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert "second" in done.stdout and "first" not in done.stdout
    bad = subprocess.run(["bash", str(path)], capture_output=True, text=True,
                         env={"SLURM_ARRAY_TASK_ID": "7", "PATH": "/usr/bin:/bin"})
    assert bad.returncode == 2 and "no task 7" in bad.stderr
