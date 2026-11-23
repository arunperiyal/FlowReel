"""--slurm and --submit of shot render, compose and film build, and the jobs commands,
with fake sbatch, squeue and sacct that record their calls."""
import json
import os
import stat

import pytest

from cli_harness import Shell
from test_cli_shot import CAMERAS, SHOT


def fake(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def sh(tmp_path, monkeypatch):
    (tmp_path / "g.yml").write_text(SHOT)
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    (tmp_path / "flowreel.yml").write_text("")              # a project (docs/project.md)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    calls = tmp_path / "calls.txt"
    monkeypatch.setenv("FLOWREEL_SBATCH", str(fake(bin_ / "sbatch",
        f'echo "sbatch $*" >> {calls}\nn=$((1310 + $(grep -c sbatch {calls}) - 1)); echo "$n;airavata"\n')))
    monkeypatch.setenv("FLOWREEL_SQUEUE", str(fake(bin_ / "squeue",
        'echo "1310_0|g|RUNNING|0:42|None"\necho "1310_[1]|g|PENDING|0:00|JobArrayTaskLimit"\n')))
    monkeypatch.setenv("FLOWREEL_SACCT", str(fake(bin_ / "sacct",
        'echo "1311|film|COMPLETED|00:01:10|0:0"\n')))
    monkeypatch.setenv("FLOWREEL_CLUSTER", "airavata")
    monkeypatch.setenv("HOME", str(tmp_path))                 # no user partition table
    monkeypatch.chdir(tmp_path)
    return Shell(tmp_path / "store")


def run(sh, line):
    status, out, err = sh.run(line)
    if status and ("OpenGL" in err or "display" in err.lower()):
        pytest.skip("off-screen rendering is not available")
    return status, out, err


def test_a_shot_not_measured_gets_a_measuring_job(sh, tmp_path):
    status, out, err = sh.run("shot render g.yml --slurm jobs/g.sh --max-running 2")
    assert status == 0, err
    assert "no measurement of a frame yet" in out and "wrote" in out and "g_measure.sh" in out
    text = (tmp_path / "jobs" / "g_measure.sh").read_text()
    assert "#SBATCH --job-name=g_measure" in text and "#SBATCH --mem=16G" in text
    assert "flowreel shot memory g.yml --frame 0 -o frames\n" in text
    assert ("flowreel shot render g.yml -o frames --slurm jobs/g.sh --submit --cluster airavata "
            "--max-running 2\n") in text
    assert not (tmp_path / "calls.txt").exists()                 # written, not submitted


def test_a_measured_shot_becomes_a_job_array_and_is_submitted(sh, tmp_path):
    status, _, err = run(sh, "shot memory g.yml -o frames")
    assert status == 0, err
    assert (tmp_path / ".flowreel" / "measured" / "frames" / "g.json").is_file()
    status, out, err = sh.run("shot render g.yml --submit --cpus 4 --after 1300")
    assert status == 0, err
    assert "6 frames in 1 task" in out and "-j 4 --threads 1" in out
    assert "submitted job 1310; log logs/g_1310_*.log" in out
    text = (tmp_path / "jobs" / "g.sh").read_text()
    assert "#SBATCH --dependency=afterok:1300" in text
    assert "  0) flowreel shot render g.yml --frames 0:5 -j 4 --threads 1 -o frames ;;" in text
    assert (tmp_path / "calls.txt").read_text().startswith("sbatch --parsable ")
    noted = json.loads((tmp_path / ".flowreel" / "jobs.json").read_text())
    assert noted[0]["job"] == "1310" and noted[0]["frames"] == [0, 1, 2, 3, 4, 5]
    assert noted[0]["folder"] == "frames/g"


def test_missing_plans_only_frames_not_drawn(sh, tmp_path):
    status, _, err = run(sh, "shot render g.yml --frames 0:3")
    assert status == 0, err
    status, out, err = sh.run("shot render g.yml --slurm r.sh --missing")
    assert status == 0, err
    assert "2 frames in 1 task" in out and "--frames 4:5" in (tmp_path / "r.sh").read_text()
    sh.run("shot render g.yml --frames 4:5")
    status, _, err = sh.run("shot render g.yml --slurm r.sh --missing")
    assert status != 0 and "every frame is drawn already" in err


def test_compose_and_film_as_jobs_after_others(sh, tmp_path):
    (tmp_path / "board.yml").write_text("size: [10, 10]\ntiles: []\n")
    status, out, err = sh.run("compose layout board.yml --slurm c.sh --scale 0.5 -j 8 "
                              "--cpus 8 --mem 32G --after 1310")
    assert status == 0, err
    assert "8 cores, 32G, 02:00:00 on airavata part1" in out
    text = (tmp_path / "c.sh").read_text()
    assert "flowreel compose layout board.yml --scale 0.5 -j 8 -o frames\n" in text
    assert "#SBATCH --dependency=afterok:1310" in text
    status, out, err = sh.run("film build --submit --preview 480 --mute --time 30m")
    assert status == 0, err
    assert "submitted job 1310" in out
    assert "flowreel film build film.yml -j 1 --preview 480 --mute\n" in \
        (tmp_path / "jobs" / "film.sh").read_text()


def test_jobs_status(sh, tmp_path):
    run(sh, "shot memory g.yml -o frames")
    sh.run("shot render g.yml --submit")
    status, out, err = sh.run("jobs status")
    assert status == 0, err
    assert "1310  g (render), submitted 00:00:0" in out
    assert "RUNNING 1, PENDING 1" in out and "frames drawn since: 0 of 6 (frames/g)" in out
    status, out, _ = sh.run("jobs status 1311")
    assert "1311  film" in out and "COMPLETED after 00:01:10, exit 0:0" in out


def test_a_task_that_started_is_counted_once(tmp_path, monkeypatch):
    from flowreel.jobs import submit
    # as a one-task array starts, squeue lists its pending record beside the task
    monkeypatch.setenv("FLOWREEL_SQUEUE", str(fake(tmp_path / "squeue",
        'echo "7_[0]|g|PENDING|0:00|None"\necho "7_0|g|RUNNING|0:02|None"\n')))
    monkeypatch.setenv("FLOWREEL_SACCT", str(fake(tmp_path / "sacct", "")))
    assert [s.job for s in submit.status(["7"])] == ["7_0"]
    states = {"7_[0]": submit.JobState("7_[0]", "g", "PENDING", "0:00", "None"),
              "7_0": submit.JobState("7_0", "g", "RUNNING", "0:02", "None")}
    assert submit._task_ids("0-2,5%2") == [0, 1, 2, 5] and submit._task_ids("x") == []
    assert submit.state_text(states["7_[0]"]) == "PENDING"
    assert submit.state_text(submit.JobState("8", "f", "PENDING", "0:00", "Dependency")) \
        == "PENDING (Dependency)"
    assert submit.state_text(states["7_0"]) == "RUNNING for 0:02"


def test_errors(sh, tmp_path):
    for line, message in [
        ("shot render g.yml --missing", "--missing is for --slurm or --submit"),
        ("shot render g.yml --slurm r.sh --time soon", "not a time: 'soon'"),
        ("shot render g.yml --slurm r.sh --cluster moon", "no cluster 'moon'"),
        ("shot render g.yml --slurm r.sh --after soon", "expected a job id"),
        ("shot render g.yml --slurm r.sh --missing --force", "not both"),
        ("film build --slurm f.sh --partition part9", "no partition 'part9'"),
        ("film build --slurm f.sh --time 4h --partition part1", "at most 03:00:00"),
    ]:
        status, _, err = sh.run(line)
        assert status != 0 and message in err, (line, err)
    os.environ["FLOWREEL_SBATCH"] = str(fake(tmp_path / "bin" / "sbatch",
                                             'echo "sbatch: error: invalid partition" >&2; exit 1\n'))
    status, _, err = sh.run("film build --submit")
    assert status != 0 and "sbatch refused" in err and "invalid partition" in err


def test_jobs_partitions_and_check(sh):
    status, out, _ = sh.run("jobs partitions --cluster airavata")
    assert status == 0 and out.splitlines()[0] == "airavata  (this machine)"
    assert "part3       3-00:00:00  128 cores, 125G" in out
    status, out, _ = run(sh, "jobs check")
    assert "auto ->" in out and status in (0, 1)
