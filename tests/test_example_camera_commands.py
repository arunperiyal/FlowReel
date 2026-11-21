"""examples/camera_commands/run.sh: import, orbit, path, project, preview and --save-vtp."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowreel.scene.camera_path import load_tracks
from flowreel.scene.views import load_views

RUN = Path(__file__).parent.parent / "examples" / "camera_commands" / "run.sh"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_example_runs_the_camera_commands(tmp_path):
    env = {**os.environ, "FLOWREEL": f"{sys.executable} -m flowreel"}
    done = subprocess.run(["sh", str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600, env=env, cwd=tmp_path)
    if done.returncode != 0 and ("OpenGL" in done.stderr or "EGL" in done.stderr):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout.splitlines()
    assert out[0] == "wrote view 'wide' (view angle 30) from trace.py to cameras.yml"
    assert out[1].startswith("wrote track 'turn': 25 views round (6, 0, -0.0003) over 48 frames")
    assert load_views(tmp_path / "ex" / "cameras.yml")["turn_00"].up == (0, 1, 0)   # axis y
    assert out[2] == "wrote track 'intro' (3 keys, frames 0 to 48) to cameras.yml"
    assert out[3].split() == ["frame", "6,0,0", "6,0.5,0"]
    assert [line.split()[0] for line in out[4:7]] == ["0", "23", "46"]
    assert out[7].startswith("5 frames of 'turn' at 160x90")
    assert out[8].startswith("saved the surfaces of 1 step (0)")
    ex = tmp_path / "ex"
    views = load_views(ex / "cameras.yml")
    assert set(load_tracks(ex / "cameras.yml", views)) == {"turn", "intro"}
    frames = sorted((ex / "frames" / "turn@preview").glob("*.png"))
    assert len(frames) == 5
    import numpy as np
    from PIL import Image
    first, last = (np.asarray(Image.open(f)).astype(int) for f in (frames[0], frames[-1]))
    assert np.abs(first - last).mean() > 5               # the camera moved
