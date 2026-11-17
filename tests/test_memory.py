"""Memory of one frame, measured in its own process, and the safe number of jobs."""
import pytest

from flowreel.scene.memory import GB, available_memory, measure, safe_jobs

from test_render import VIEWS, toy_shot


def test_safe_jobs_is_limited_by_memory_then_cores():
    assert safe_jobs(2 * GB, 100 * GB, cpus=128) == 40           # 80 GB / 2 GB
    assert safe_jobs(int(0.7 * GB), 100 * GB, cpus=48) == 48      # cores limit
    assert safe_jobs(1 * GB, 100 * GB, cpus=48, threads=4) == 12
    assert safe_jobs(64 * GB, 16 * GB, cpus=8) == 1               # never less than one


def test_available_memory_is_positive():
    assert available_memory() > 0


def test_measure_draws_one_frame_in_a_process(toy_source):
    try:
        report = measure(toy_shot(), 1, toy_source, views=VIEWS, threads=1)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert report.frame == 1 and report.threads == 1
    assert 10 * 1024 ** 2 < report.peak_bytes < 8 * GB              # Python and VTK at least
    assert report.estimate_bytes == int(1e-6 * GB)                 # the toy's own estimate
    assert report.jobs >= 1 and "suggested jobs: -j" in report.text()


def test_measure_checks_the_frame(toy_source):
    with pytest.raises(IndexError, match="outside"):
        measure(toy_shot(), 9, toy_source, views=VIEWS)
