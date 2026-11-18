"""examples/riser500/run.py: the generated riser case, read through a window and drawn."""
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "riser500" / "run.py"


def test_example_runs_in_draft(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex"), "--draft"],
                          capture_output=True, text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout
    assert "(26 times less)" in out
    assert "through the window: 0.61 MB" in out and "a case 250 long: 0.61 MB" in out
    assert "travel frame 0: window x 10.0 to 30.0" in out
    for shot in ("travel", "span", "pendulum"):
        assert f"{shot}: 2 drawn" in out
