"""jobs.spec: a job held against its partition."""
from dataclasses import replace

import pytest

from flowreel.jobs import partitions as p
from flowreel.jobs.spec import JobError, JobSpec

GB = 1024 ** 3
CLUSTERS = p.load(user=p.Path("/nonexistent.yml"))
PART1 = CLUSTERS["airavata"].partition("part1")
MEDIUM = CLUSTERS["param_shakti"].partition("medium")
SHARED = CLUSTERS["param_shakti"].partition("shared")


def job(**kw):
    return JobSpec(**{"name": "reveal", "partition": PART1, "cpus": 16, "memory": 32 * GB,
                      "time": 7200, **kw})


def test_a_job_that_fits():
    j = job().check()
    assert j.log_pattern == "logs/%x_%j.log"
    assert job(tasks=10, max_running=4).check().log_pattern == "logs/%x_%A_%a.log"
    assert job(log="out/%j.txt").log_pattern == "out/%j.txt"
    assert job(memory=None, after=("1301", "1302_4")).check().after == ("1301", "1302_4")


@pytest.mark.parametrize("change, message", [
    ({"cpus": 200}, "partition part1 of airavata gives a job at most 128 cores; asked 200"),
    ({"memory": 200 * GB}, "has 125G on a node; asked 200G"),
    ({"time": 4 * 3600}, "runs a job for at most 03:00:00; asked 04:00:00"),
    ({"cpus": 0}, "at least 1 core"),
    ({"time": 0}, "time must be positive"),
    ({"name": "my render"}, "one word"),
    ({"tasks": 0}, "at least 1 task"),
    ({"max_running": 2}, "max_running is for a job array"),
    ({"tasks": 4, "max_running": 0}, "max_running must be at least 1"),
    ({"after": ("soon",)}, "Slurm job ids"),
])
def test_limits_are_named(change, message):
    with pytest.raises(JobError, match=message.replace("(", r"\(").replace(")", r"\)")):
        job(**change).check()


def test_whole_node_partitions_and_unknown_limits():
    with pytest.raises(JobError, match="whole nodes to MPI jobs.*shared partition"):
        job(partition=MEDIUM, time=3600).check()
    with pytest.raises(JobError, match="at most 36 cores; asked 40"):
        job(partition=SHARED, cpus=40).check()
    # Param Shakti's memory is not recorded, so no memory limit is checked there
    assert replace(job(partition=SHARED, memory=500 * GB)).check()
