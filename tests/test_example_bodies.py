"""examples/bodies/run.py runs from a clean folder and follows the riser on its bend."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "bodies" / "run.py"


def test_example_declares_measures_and_follows(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout
    assert "axis: x" in out and "diameter: 1 " in out          # measured by project init
    assert "declared: riser (zone cyl), ball (zone ball)" in out
    for focal_y, bend in re.findall(r"focal \([\d.]+, ([\d.]+), [\d.]+\); bend there ([\d.]+)", out):
        assert abs(float(focal_y) - float(bend)) < 0.01
    assert "riser_travel: 12 drawn, 0 skipped" in out
