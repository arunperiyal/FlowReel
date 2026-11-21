"""Cores and memory of the running process, inside and outside a Slurm job."""
import pytest

from flowreel.jobs import resources as R
from flowreel.jobs.resources import GB, cgroup_room, resources
from flowreel.scene import memory, rendering

JOB = "/system.slice/slurmstepd.scope/job_1301/step_0"


@pytest.fixture
def machine(tmp_path):
    """A fake /proc and /sys/fs/cgroup under ``tmp_path``; returns a builder."""
    def make(free_gb=100, v2=None, v1=None, path=JOB):
        (tmp_path / "meminfo").write_text(
            f"MemTotal:       131072000 kB\nMemAvailable:   {free_gb * 1024 ** 2} kB\n")
        lines = []
        root = tmp_path / "cgroup"
        if v2 is not None:                       # {relative folder: (max, current)}
            lines.append(f"0::{path}")
            for folder, (limit, current) in v2.items():
                d = root / folder
                d.mkdir(parents=True, exist_ok=True)
                (d / "memory.max").write_text(f"{limit}\n")
                (d / "memory.current").write_text(f"{current}\n")
        if v1 is not None:
            lines.append(f"4:memory:{path}")
            for folder, (limit, usage) in v1.items():
                d = root / "memory" / folder
                d.mkdir(parents=True, exist_ok=True)
                (d / "memory.limit_in_bytes").write_text(f"{limit}\n")
                (d / "memory.usage_in_bytes").write_text(f"{usage}\n")
        (tmp_path / "cgroup.txt").write_text("\n".join(lines) + "\n")
        return dict(meminfo=tmp_path / "meminfo", proc_cgroup=tmp_path / "cgroup.txt",
                    cgroup_root=root)
    return make


def slurm(**extra):
    return {"SLURM_JOB_ID": "1301", **extra}


def test_outside_slurm_the_machine_free_memory_and_cores(machine):
    have = resources({}, affinity=16, **machine(free_gb=22))
    assert have == R.Resources(16, 22 * GB, "CPU affinity", "MemAvailable", None)
    assert have.text() == ("this machine: 16 cores, 22.0 GB "
                           "(cores from CPU affinity, memory from MemAvailable)")


def test_outside_slurm_slurm_variables_are_ignored(machine):
    env = {"SLURM_CPUS_PER_TASK": "2", "SLURM_MEM_PER_NODE": "1000"}   # no job id
    have = resources(env, affinity=16, **machine(free_gb=22))
    assert (have.cores, have.memory_bytes, have.job) == (16, 22 * GB, None)


def test_slurm_job_mem_per_node_and_cpus_per_task(machine):
    env = slurm(SLURM_CPUS_PER_TASK="16", SLURM_CPUS_ON_NODE="16",
                SLURM_MEM_PER_NODE="32768")
    have = resources(env, affinity=128, **machine(free_gb=100))
    assert have == R.Resources(16, 32 * GB, "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE",
                               "1301")
    assert have.text().startswith("Slurm job 1301: 16 cores, 32.0 GB")


def test_slurm_mem_per_cpu_times_the_cores(machine):
    env = slurm(SLURM_CPUS_ON_NODE="8", SLURM_MEM_PER_CPU="2048")
    have = resources(env, affinity=128, **machine())
    assert (have.cores, have.cores_from) == (8, "SLURM_CPUS_ON_NODE")
    assert (have.memory_bytes, have.memory_from) == (16 * GB, "SLURM_MEM_PER_CPU")


def test_affinity_smaller_than_the_slurm_count_wins(machine):
    have = resources(slurm(SLURM_CPUS_PER_TASK="16"), affinity=4, **machine())
    assert (have.cores, have.cores_from) == (4, "CPU affinity")


def test_an_array_task_is_named_by_job_and_task(machine):
    env = slurm(SLURM_ARRAY_JOB_ID="1300", SLURM_ARRAY_TASK_ID="4")
    assert resources(env, affinity=2, **machine()).where == "Slurm job 1300_4"


def test_never_more_than_mem_available(machine):
    env = slurm(SLURM_MEM_PER_NODE=str(64 * 1024))
    have = resources(env, affinity=8, **machine(free_gb=10,
                                                v2={JOB[1:]: (64 * GB, 1 * GB)}))
    assert (have.memory_bytes, have.memory_from) == (10 * GB, "MemAvailable")


def test_cgroup_v2_limit_minus_current(machine):
    env = slurm(SLURM_MEM_PER_NODE=str(32 * 1024))
    files = machine(v2={JOB[1:]: (32 * GB, 2 * GB)})
    have = resources(env, affinity=8, **files)
    assert (have.memory_bytes, have.memory_from) == (30 * GB, "cgroup memory.max")


def test_cgroup_v2_the_tightest_level_counts(machine):
    files = machine(v2={JOB[1:]: ("max", 1 * GB),
                        "system.slice/slurmstepd.scope/job_1301": (12 * GB, 4 * GB),
                        "system.slice": (50 * GB, 20 * GB)})
    assert cgroup_room(files["proc_cgroup"], files["cgroup_root"]) == \
        (8 * GB, "cgroup memory.max")


def test_cgroup_v2_in_a_namespace_reads_the_root(machine):
    files = machine(v2={"": (6 * GB, GB)}, path="/")      # /sys/fs/cgroup/memory.max
    have = resources({}, affinity=4, **files)              # a container, not Slurm
    assert (have.memory_bytes, have.memory_from) == (5 * GB, "cgroup memory.max")


def test_cgroup_v1_limit_minus_usage(machine):
    files = machine(v1={JOB[1:]: (24 * GB, 4 * GB)})
    have = resources(slurm(SLURM_MEM_PER_NODE=str(32 * 1024)), affinity=8, **files)
    assert (have.memory_bytes, have.memory_from) == (20 * GB, "cgroup memory.limit_in_bytes")


def test_cgroup_v1_no_limit_is_ignored(machine):
    files = machine(free_gb=50, v1={JOB[1:]: (9223372036854771712, GB)})
    have = resources(slurm(), affinity=8, **files)
    assert (have.memory_bytes, have.memory_from) == (50 * GB, "MemAvailable")


def test_no_cgroup_file_no_limit(tmp_path):
    assert cgroup_room(tmp_path / "missing", tmp_path) is None


def test_slurm_limit_larger_than_free_memory_is_capped(machine):
    have = resources(slurm(SLURM_MEM_PER_NODE=str(200 * 1024)), affinity=8,
                     **machine(free_gb=120))
    assert have.memory_bytes == 120 * GB


def test_the_real_process():
    have = resources()
    assert have.cores >= 1 and have.memory_bytes > 0 and have.memory_from


def test_renders_use_the_job_resources(monkeypatch):
    fake = R.Resources(6, 3 * GB, "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE", "7")
    monkeypatch.setattr(rendering, "resources", lambda: fake)
    monkeypatch.setattr(memory, "resources", lambda: fake)
    assert rendering.default_threads(1) == 4 and rendering.default_threads(2) == 3
    assert rendering.default_threads(12) == 1
    assert memory.available_memory() == 3 * GB


def test_memory_report_says_where_the_numbers_came_from():
    report = memory.MemoryReport(0, GB, 1.0, None, 32 * GB, 16, 4, 16,
                                 "Slurm job 1301, SLURM_MEM_PER_NODE")
    assert report.text().splitlines()[1] == (
        "free memory 32.0 GB, 16 cores (Slurm job 1301, SLURM_MEM_PER_NODE); "
        "measured with 4 threads")
