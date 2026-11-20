# Rendering on a Slurm cluster

Phase 5. A long render runs on a compute node: FlowReel writes the job script and hands
it to `sbatch`, so nothing is written by hand. This page covers the pieces under that:
the clusters FlowReel knows, the job it asks for, and the script it writes. The commands
that use them (`shot render --slurm FILE --submit`) come later in the phase.

The first cluster is airavata's `node1`: 128 cores, 125 GB, no GPU. It draws off-screen
with Mesa EGL on the CPU, as the prototype's renders did (checked 2026-11-21: a frame of
640 x 360 in 1.9 s on 4 cores). The node is shared with simulation jobs, so a render
asks for part of it, not all.

## Clusters and partitions

FlowReel keeps its own table, `src/flowreel/jobs/partitions.yml`:

| Cluster | Partition | Time | Node | Note |
|---|---|---|---|---|
| `airavata` | `part1` | 3 h | 128 cores, 125 GB | |
| | `part2` | 24 h | 128 cores, 125 GB | |
| | `part3` | 72 h | 128 cores, 125 GB | |
| `param_shakti` | `shared` | 72 h | 40 cores (36 per job) | the one for renders |
| | `medium`, `large` | 72 h, 168 h | 40 cores, whole nodes | MPI only; refused for renders |
| | `gpu` | 72 h | | |

The cluster is the one given with `--cluster NAME`, else the `FLOWREEL_CLUSTER`
environment variable, else the one whose `hosts` match this machine's name (on
airavata's login node and on `node1`, `airavata`). When no partition is named, a job
goes to the shortest shared partition that takes its time, cores and memory: a 2-hour
render on airavata goes to `part1`, a 4-hour one to `part2`.

### Adding a cluster

`~/.flowreel/partitions.yml`, written the same way, adds clusters and replaces
partitions; the rest of the table stays.

```yaml
workstation:
  hosts: [ws*]                 # shell patterns of host names that pick it
  partitions:
    local: {time: 7d, cpus: 48, memory: 250G, note: 'the lab workstation'}
airavata:
  partitions:
    part1: {time: 6h, cpus: 128, memory: 125G}   # replaces part1 only
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `hosts` | list of patterns | `[]` | host names that pick the cluster; empty: only by name |
| `time` | time | required | the longest a job may run: `90m`, `3h`, `2d`, `02:30:00`, `1-12:00:00` (a bare number is minutes, as in Slurm) |
| `cpus` | whole number | none | cores of one node |
| `memory` | size | none | memory of one node: `125G`, `500M` (a bare number is megabytes, as in Slurm) |
| `max_cpus` | whole number | `cpus` | the most cores one job may ask for |
| `shared` | true or false | `true` | whether jobs share a node; renders need a shared partition |
| `note` | text | | shown in the partition list |

A limit left out is not checked. A typo in a key is reported with the file, the key
path and the nearest valid key.

## The job

A render is one process tree on one node: one job of some cores and memory for some
time, or a job array of such jobs with at most N running at once, so that it takes part
of a shared node. Before anything is written, the job is held against its partition,
and an error names the limit it breaks:

```text
partition part1 of airavata runs a job for at most 03:00:00; asked 04:00:00
partition part1 of airavata gives a job at most 128 cores; asked 200
partition medium of param_shakti gives whole nodes to MPI jobs (...); a render is one
process tree, so use a shared partition
```

## The script

```bash
#!/bin/bash
# Written by flowreel 0.0.1: flowreel shot render reveal.yml --slurm render.sh.
# Submit with: sbatch THIS_FILE. Frames already drawn are skipped, so a job
# that stopped can be submitted again as it is.
#SBATCH --job-name=reveal
#SBATCH --partition=part1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --chdir=/scratch/.../flowreel_video
#SBATCH --output=logs/%x_%j.log

set -euo pipefail
export PATH=/home/arunperiyal/.conda/envs/flexflow_env/bin:"$PATH"
unset DISPLAY                 # drawn off-screen (EGL or OSMesa)
echo "flowreel job ${SLURM_JOB_ID:-?} on $(hostname): ${SLURM_CPUS_PER_TASK:-?} cores, started $(date)"
python -m flowreel.jobs.check
flowreel shot render reveal.yml -j 8
echo "done $(date)"
```

- **The environment it was written from** comes first on the path, so the job runs the
  same FlowReel and finds the environment's ffmpeg, whatever the node's own setup.
- **`--chdir`** is the project folder, so the shot's relative paths and the log resolve
  there wherever `sbatch` is run from.
- **The log folder** (`logs/` by default) is made when the script is written. Slurm
  does not make it, and a job whose log cannot be opened fails without a word.
- **The off-screen check** draws a tiny picture with each backend first, so a node
  without OpenGL fails in seconds, not after the data is loaded.
- **A job array** runs each task's commands from a `case` on `SLURM_ARRAY_TASK_ID`, with
  `--array=0-9%4` for ten tasks, four at a time.
- **A chain**: `--dependency=afterok:1301:1302` starts a job only when those ended well,
  so composes and the film build can wait for the renders.

## Splitting a render

A render becomes a job array, sized from what one frame of the shot costs.

**Measured, not guessed.** Every render that draws frames keeps the largest peak memory
and the middle time of its frames in `.measured.json` in the shot's frame folder
(`frames/reveal/`; a draft has its own, since it costs less), and `shot memory SHOT -o
OUT` keeps the frame it draws. So the next render, on any machine that shares the
folder, is sized from the last one. A shot with no measurement yet gets a small first
job: it measures one frame on the node (4 cores, 16 GB, 30 minutes), then plans and
submits the render.

**Per task.** 16 cores unless asked; as many frames drawn at once (`-j`) as the cores
take at `--threads` each (1 by default: Mesa's renderer draws one frame per core), and
no more than the memory holds, each frame getting its measured peak with 20% to spare.
Memory left out is asked for to fit those jobs, in whole GB, and jobs are cut down when
a node would not hold them.

**Tasks.** Consecutive runs of frames, about eight frames per job: a task loads Python,
VTK and the data once for many frames, and one cut short loses little. `--max-running
N` lets at most N tasks run at once, so a render takes part of a shared node and leaves
the rest to simulations.

**Time.** The measured seconds a frame, times the rounds a task draws, half as much
again, and ten minutes for starting and opening the data; the job goes to the shortest
partition that takes it. A task that would outrun the longest partition is cut into
smaller ones. A time given with `--time` is used as it is, with a warning when the
estimate does not fit.

```text
121 frames in 1 task of up to 121 frames
each task: 16 cores, 14G, -j 16 --threads 1, 00:11:12 on airavata part1 (drawing about 00:00:48)
one frame: 0.70 GB and 6.0 s a frame (12 frames, 1 thread, node1, 2026-11-21 04:00)
```

**Resume.** Frames drawn with their key are skipped, so a render that was cancelled or
ran out of time is submitted again as it is. `--missing` goes further and plans tasks
for the missing frames only (`flowreel.scene.rendering.missing` works out the keys
without drawing).

From Python, `flowreel.jobs.partitions` (`load`, `find`, `parse_time`, `parse_memory`),
`flowreel.jobs.spec.JobSpec`, `flowreel.jobs.script` (`job_script`, `write`),
`flowreel.jobs.measured` and `flowreel.jobs.split` (`plan_render`, `render_job`,
`render_commands`, `measure_job`) do the same.
