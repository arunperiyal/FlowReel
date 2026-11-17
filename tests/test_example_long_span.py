"""examples/long_span/run.py: a window travelling along a generated long case."""
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "long_span" / "run.py"


def test_example_reads_a_window_and_draws_the_span(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout
    assert "(9 times less)" in out
    assert "frame 0: window x 10.0 to 30.0, 720 cells read" in out
    assert "frame 9: window x 170.0 to 190.0, 720 cells read" in out
    assert "travel: 10 drawn" in out and "whole: 1 drawn" in out
