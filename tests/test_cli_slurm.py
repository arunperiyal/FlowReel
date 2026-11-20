"""--slurm and --submit of shot render, compose and film build, and the jobs commands,
with fake sbatch, squeue and sacct that record their calls."""
import json
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
    assert (tmp_path / "frames" / "g" / ".measured.json").is_file()
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


def test_errors(sh, tmp_path):
    for line, message in [
        ("shot render g.yml --missing", "--missing is for --slurm or --submit"),
        ("shot render g.yml --slurm r.sh --time soon", "not a time: 'soon'"),
        ("shot render g.yml --slurm r.sh --cluster moon", "no cluster 'moon'"),
        ("shot render g.yml --slurm r.sh --after soon", "expected a job id"),
        ("shot render g.yml --slurm r.sh --missing --force", "not both"),
    ]:
        status, _, err = sh.run(line)
        assert status != 0 and message in err, (line, err)
