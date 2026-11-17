"""examples/bodies/run.py runs from a clean folder and follows the riser on its bend."""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
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
    assert ("displacement: 50 rows, nodes [0, 1, 2, 3, 4]; dy at t = 0.3 by station: "
            "0: 0.000, 10: 1.009, 20: 1.427, 30: 1.009, 40: 0.000") in out
    for focal_y, bend in re.findall(r"focal \([\d.]+, ([\d.]+), [\d.]+\); bend there ([\d.]+)", out):
        assert abs(float(focal_y) - float(bend)) < 0.01
    assert "riser_travel: 12 drawn, 0 skipped" in out
    assert "riser_span: 9 drawn, 0 skipped" in out
    assert "pendulum: 10 drawn, 0 skipped" in out
    # the pivot is the riser's centre at station 20, y = 1.5; lowest = 1.5 - 4 cos a - 0.6
    lows = [float(v) for v in out.split("bob's lowest point by frame: ")[1].split("\n")[0].split(", ")]
    angles = 0.6 * np.sin(2 * np.pi * np.arange(10) * 0.1)
    assert np.allclose(lows, 1.5 - 4 * np.cos(angles) - 0.6, atol=0.003)
    # 2 + dy at mid-span, dy = 1.5 sin(2 pi t) at t = 0.1 ... 0.9
    assert ("arrow length by frame: 2.882, 3.427, 3.427, 2.882, 2.000, 1.118, 0.573, "
            "0.573, 1.118") in out
