"""Write a Slurm job script for a render split into four tasks, without submitting it.

Usage: python run.py [DIR]   (default ./slurm_script_example)

Needs no cluster: it uses FlowReel's partition table (airavata's part1 here), holds the
job against it, and writes DIR/render.sh and DIR/logs/. On airavata, `sbatch
--test-only DIR/render.sh` says when and where it would start. A job that asks for too
much is refused with the limit it breaks, which the second part shows.
"""
import sys
from pathlib import Path

from flowreel.jobs import partitions
from flowreel.jobs.script import job_script, write
from flowreel.jobs.spec import JobError, JobSpec

GB = 1024 ** 3


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    airavata = partitions.load()["airavata"]
    time = partitions.parse_time("2h")
    spec = JobSpec("wake", airavata.fitting(time, 8, 16 * GB), cpus=8, memory=16 * GB,
                   time=time, tasks=4, max_running=2)
    frames = ["0:29", "30:59", "60:89", "90:120"]
    tasks = [[["flowreel", "shot", "render", "wake.yml", "--frames", f, "-j", "4"]] for f in frames]
    text = job_script(spec, tasks=tasks, workdir=folder, written_by="examples/slurm_script")
    print(f"wrote {write(folder / 'render.sh', text, spec, folder).name} "
          f"for partition {spec.partition.name}")
    try:
        JobSpec("wake", airavata.partition("part1"), cpus=8, time=partitions.parse_time("5h")).check()
    except JobError as error:
        print(f"refused: {error}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("slurm_script_example"))
