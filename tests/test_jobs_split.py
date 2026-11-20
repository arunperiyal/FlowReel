"""jobs.split: a render planned as a job array, from one frame's measured cost."""
import pytest

from flowreel.jobs import partitions as p
from flowreel.jobs.measured import Measured
from flowreel.jobs.script import job_script
from flowreel.jobs.split import (NeedMeasure, frames_spec, plan_render, render_commands,
                                 render_job)

GB = 1024 ** 3
AIRAVATA = p.load(user=p.Path("/nonexistent.yml"))["airavata"]
BARE = Measured(int(0.7 * GB), 6.0, 1, 12, "node1", "2026-11-21 04:00")       # a bare frame
HELICAL = Measured(int(2.2 * GB), 15.0, 1, 12, "node1", "2026-11-21 04:00")


def test_frames_spec():
    assert frames_spec([0, 1, 2, 3]) == "0:3"
    assert frames_spec([0, 1, 2, 5, 7, 8]) == "0:2,5,7:8"
    assert frames_spec([4]) == "4"


def test_a_bare_reveal():
    """121 frames; 16 cores, 16 jobs of 0.7 GB (0.875 GB at 80%): 14 GB; 128 frames a
    task -> one task; 8 rounds of 6 s with a 1.5 margin and 10 minutes to start."""
    plan = plan_render(list(range(121)), BARE, AIRAVATA)
    assert (plan.cpus, plan.jobs, plan.threads, plan.memory) == (16, 16, 1, 14 * GB)
    assert plan.runs == [list(range(121))]
    assert plan.estimate == 8 * 6.0 and plan.time == round(48 * 1.5 + 600)
    assert plan.partition.name == "part1" and plan.max_running is None
    assert "121 frames in 1 task of up to 121 frames" in plan.text()
    assert "each task: 16 cores, 14G, -j 16 --threads 1, 00:11:12 on airavata part1" in plan.text()


def test_many_frames_go_in_runs_and_at_most_n_at_once():
    plan = plan_render(list(range(600)), HELICAL, AIRAVATA, cpus=32, max_running=3)
    assert plan.jobs == 32 and plan.memory == 88 * GB            # 32 x 2.75 GB
    assert [len(r) for r in plan.runs] == [256, 256, 88]
    assert plan.runs[1][0] == 256 and plan.max_running == 3
    assert plan.text().startswith("600 frames in 3 tasks of up to 256 frames, 3 at once")


def test_memory_given_limits_the_jobs():
    plan = plan_render(list(range(100)), HELICAL, AIRAVATA, cpus=32, memory=20 * GB)
    assert plan.jobs == 7 and plan.memory == 20 * GB             # 20 / 2.75
    with pytest.raises(ValueError, match="one frame needs about 3G .* asked 2G"):
        plan_render([0], HELICAL, AIRAVATA, memory=2 * GB)


def test_more_jobs_than_a_node_holds_are_cut_down():
    big = Measured(int(10 * GB), 30.0, 1, 1, "node1", "x")
    plan = plan_render(list(range(50)), big, AIRAVATA, cpus=64)
    assert plan.jobs == 10 and plan.memory == 125 * GB           # 125 / 12.5


def test_time_given_and_long_frames():
    plan = plan_render(list(range(121)), BARE, AIRAVATA, time=600)
    assert plan.time == 600 and plan.partition.name == "part1"
    assert any("may need 00:10:48, more than the 00:10:00 asked for" in n for n in plan.notes)
    slow = Measured(int(GB), 20 * 3600.0, 1, 1, "node1", "x")     # 20 h a frame
    plan = plan_render(list(range(64)), slow, AIRAVATA, cpus=16)
    # 4 rounds (80 h, 120 h with the margin) outrun part3's 72 h: cut to 2 rounds a task
    assert [len(r) for r in plan.runs] == [32, 32]
    assert plan.partition.name == "part3" and plan.time == round(40 * 3600 * 1.5 + 600)
    with pytest.raises(ValueError, match="longer than airavata's longest partition"):
        plan_render([0], Measured(int(GB), 80 * 3600.0, 1, 1, "n", "x"), AIRAVATA)


def test_threads_and_a_named_partition():
    plan = plan_render(list(range(40)), BARE, AIRAVATA, cpus=16, threads=4, partition="part3")
    assert plan.jobs == 4 and plan.partition.name == "part3"
    # 6 s at 1 thread -> 1.5 s at 4; 4 jobs x 8 rounds = 32 frames a task, 8 rounds
    assert [len(r) for r in plan.runs] == [32, 8] and plan.estimate == 8 * 1.5


def test_no_measurement():
    with pytest.raises(NeedMeasure, match="shot memory"):
        plan_render([0, 1], None, AIRAVATA)


def test_the_job_and_its_script(tmp_path):
    plan = plan_render(list(range(300)), BARE, AIRAVATA, max_running=2)
    spec = render_job(plan, "reveal", after=[1301])
    assert (spec.tasks, spec.max_running, spec.after) == (3, 2, ("1301",))
    tasks = render_commands(plan, "shots/reveal.yml", scale=0.5, backend="egl")
    assert tasks[2] == [["flowreel", "shot", "render", "shots/reveal.yml", "--frames", "256:299",
                         "-j", "16", "--threads", "1", "-o", "frames", "--scale", "0.5",
                         "--backend", "egl"]]
    text = job_script(spec, tasks=tasks, workdir=tmp_path)
    assert "#SBATCH --array=0-2%2" in text and "--frames 128:255 -j 16" in text


def test_a_measuring_job_then_the_render(tmp_path):
    from flowreel.jobs.split import measure_job
    spec, commands = measure_job(AIRAVATA, "reveal", "reveal.yml",
                                 ["flowreel", "shot", "render", "reveal.yml", "--submit"],
                                 scale=0.5)
    assert (spec.name, spec.cpus, spec.memory, spec.partition.name) == (
        "reveal_measure", 4, 16 * GB, "part1")
    assert commands == [["flowreel", "shot", "memory", "reveal.yml", "--frame", "0", "-o",
                         "frames", "--scale", "0.5"],
                        ["flowreel", "shot", "render", "reveal.yml", "--submit"]]
    text = job_script(spec, commands, workdir=tmp_path)
    assert text.index("shot memory") < text.index("shot render reveal.yml --submit")
