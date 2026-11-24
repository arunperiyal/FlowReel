import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

EXAMPLES = Path(__file__).parent.parent / "examples"


def run(script, *args):
    done = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "EGL" in done.stderr):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout


def test_example_draws_something(tmp_path):
    out = run(EXAMPLES / "flow_layers" / "run.py", tmp_path / "ex")
    assert out.count("flow_layers_") == 3
    import numpy as np
    picture = np.asarray(Image.open(tmp_path / "ex" / "flow_layers_12.png").convert("RGB"))
    assert picture.shape == (360, 640, 3) and (picture.max(axis=2) > 40).mean() > 0.05
    assert (tmp_path / "ex" / "data" / "vortex" / "domain.yml").is_file()


def test_marker_example_draws_something():
    from flowreel.scene import render_frame
    from flowreel.scene.shot import load
    folder = EXAMPLES / "marker_layers"
    try:
        picture = render_frame(load(folder / "shots" / "marker_layers.yml"), 12)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert picture.shape == (360, 640, 3) and (picture.max(axis=2) > 40).mean() > 0.02
