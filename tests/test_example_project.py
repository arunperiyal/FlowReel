"""examples/project/run.sh: project init with a data link, a render from shots/, info, clean."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "project" / "run.sh"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_example_makes_uses_and_cleans_a_project(tmp_path):
    env = {**os.environ, "FLOWREEL": f"{sys.executable} -m flowreel"}
    done = subprocess.run(["sh", str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600, env=env, cwd=tmp_path)
    if done.returncode != 0 and ("OpenGL" in done.stderr or "EGL" in done.stderr):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    root = tmp_path / "ex" / "film"
    out = done.stdout
    assert "linked" in out and (root / "data" / "case").is_symlink()
    assert "2 rendered" in out and f"-> {root / 'frames' / 'cylinder@160x90'}" in out
    assert "shots/cylinder.yml: cylinder, 0 frames drawn (2 in drafts)" in out
    assert "would remove frames/" in out
    assert sorted(p.name for p in (root / "frames" / "cylinder@160x90").glob("*.png")) == \
        ["frame_00000.png", "frame_00011.png"]
    assert not (root / "shots" / "frames").exists()
