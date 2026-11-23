"""Phase 5's check, in this repository: a generated shot submitted with
``flowreel shot render --submit`` and run by a fake ``sbatch``
(``examples/slurm_project/fake_sbatch.py``) that runs each job here, as Slurm would on
a node.

- A shot not measured yet: the measuring job measures one frame, then submits the render
  itself, which draws every frame.
- A render cut short (only its first task runs) is submitted again with ``--missing``:
  only the frames left are drawn, and none drawn before is touched.

The run on airavata's node1 is recorded in plan/phases.md under Phase 5's done line.
"""
import json
import os
import sys
from pathlib import Path

import pytest

from cli_harness import Shell
from test_cli_shot import CAMERAS

FAKE = Path(__file__).parent.parent / "examples" / "slurm_project" / "fake_sbatch.py"
SHOT = """name: g
source: geometry:grooved_cylinder
time: {frozen: 0, frames: 20}
camera: {view: main}
size: [64, 48]
antialias: none
layers:
  - {type: outline, width: 2}
  - {type: geometry, body: grooved_cylinder, colour: "#ff0000"}
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "g.yml").write_text(SHOT)
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    (tmp_path / "flowreel.yml").write_text("")              # a project (docs/guide/projects/project.md)
    sbatch = tmp_path / "sbatch"
    sbatch.write_text(f"#!/bin/bash\nexec {sys.executable} {FAKE} \"$@\"\n")
    sbatch.chmod(0o755)
    monkeypatch.setenv("FLOWREEL_SBATCH", str(sbatch))
    squeue = tmp_path / "squeue"                     # the fake's jobs are over at once
    squeue.write_text("#!/bin/bash\n")
    squeue.chmod(0o755)
    monkeypatch.setenv("FLOWREEL_SQUEUE", str(squeue))
    monkeypatch.setenv("FLOWREEL_SACCT", str(squeue))
    monkeypatch.setenv("FAKE_SBATCH_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("FLOWREEL_CLUSTER", "airavata")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def frames(folder):
    return {p.name: p.stat().st_mtime_ns for p in sorted((folder / "frames" / "g").glob("frame_*.png"))}


def submit(sh, line):
    status, out, err = sh.run(line)
    assert status == 0, err
    return out


def test_measure_then_render_then_resume(project, monkeypatch):
    sh = Shell(project / "store")
    out = submit(sh, "shot render g.yml --submit --cpus 2")
    assert "submitted job 1001" in out and "measuring job" in out
    log = (project / "logs" / "g_measure_1001.log").read_text()
    if "does NOT work" in log or "no off-screen" in log:
        pytest.skip("off-screen rendering is not available")
    assert "jobs.check" not in log and "auto ->" in log                 # the check ran first
    assert "frame 0: peak" in log and "submitted job 1002" in log       # measured, then submitted
    assert "20 frames in 2 tasks of up to 16 frames" in log
    assert len(frames(project)) == 20
    noted = json.loads((project / ".flowreel" / "jobs.json").read_text())
    assert sorted((n["job"], n["kind"]) for n in noted) == [("1001", "measure"), ("1002", "render")]
    assert "task 1 on" in (project / "logs" / "g_1002_1.log").read_text()

    # Draw again with --force, but only the first task runs: a render cut short.
    before = frames(project)
    monkeypatch.setenv("FAKE_SBATCH_TASKS", "0")
    out = submit(sh, "shot render g.yml --submit --cpus 2 --force")
    assert "20 frames in 2 tasks" in out
    after = frames(project)
    assert all(after[f] != before[f] for f in list(after)[:16])         # task 0 drew 0..15
    assert all(after[f] == before[f] for f in list(after)[16:])         # task 1 never ran
    # The frames left behind are those of task 1: a key exists for them, so --missing would
    # find nothing; delete them to stand for frames never drawn.
    for f in list(after)[16:]:
        (project / "frames" / "g" / f).unlink()
    monkeypatch.delenv("FAKE_SBATCH_TASKS")
    kept = frames(project)
    out = submit(sh, "shot render g.yml --submit --missing --cpus 2")
    assert "4 frames in 1 task" in out and "--frames 16:19" in (project / "jobs" / "g.sh").read_text()
    final = frames(project)
    assert len(final) == 20 and all(final[f] == kept[f] for f in kept)  # nothing redrawn
    status, out, err = sh.run("jobs status")
    assert status == 0, err
    assert "1001  g_measure (measure)" in out and "1004  g (render)" in out
    # The fake runs a job before sbatch returns, so the frames predate the job's note and
    # count as drawn before it; on Slurm the note comes first. Only the shape is checked.
    assert "of 4 (frames/g)" in out and "of 20 (frames/g)" in out
