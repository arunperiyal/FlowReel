"""examples/compose_layout/run.py: frame folders tiled, then a shot at three stations."""
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "compose_layout" / "run.py"


def test_example_composes_layouts(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert lines[:4] == ["compare: 8 composed, 0 skipped, 960 x 270",
                         "grid: 8 composed, 0 skipped, 960 x 540",
                         "compare: 0 composed, 8 skipped, 960 x 270",
                         "grid: 0 composed, 8 skipped, 960 x 540"]
    assert lines[4] == "stations: 4 composed, 0 skipped, 960 x 180"
    assert (tmp_path / "ex" / "frames" / "window_station100@320x180" / "frame_00003.png").exists()
