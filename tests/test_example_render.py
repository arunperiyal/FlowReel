"""examples/render_shot/run.py runs from a clean folder, and a second run skips all."""
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "render_shot" / "run.py"


def run(cwd):
    done = subprocess.run([sys.executable, str(RUN)], cwd=cwd, capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout


def test_example_renders_then_skips(tmp_path):
    first = run(tmp_path)
    assert "render_shot: 12 drawn, 0 skipped" in first
    assert "render_shot@320x180: 12 drawn, 0 skipped" in first
    assert "suggested jobs: -j" in first
    assert len(list((tmp_path / "frames" / "render_shot").glob("frame_*.png"))) == 12
    second = run(tmp_path)
    assert "render_shot: 0 drawn, 12 skipped" in second
