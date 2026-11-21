"""examples/camera_editor/run.py: a scripted editor session, then the same away from the data."""
import subprocess
import sys
from pathlib import Path

import pytest

from flowreel.scene.camera_path import load_tracks
from flowreel.scene.views import load_views

RUN = Path(__file__).parent.parent / "examples" / "camera_editor" / "run.py"


def test_example_picks_a_track(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=300)
    if done.returncode != 0 and ("OpenGL" in done.stderr or "EGL" in done.stderr):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert lines[:3] == [
        "played 48 frames",
        "key at frame 0: approach_0000 from (3.0, 2.5, 3.2)",
        "key at frame 47: approach_0047 from (1.0, -1.7, 1.2)"]
    assert lines[3].startswith("saved surfaces of steps [0, 1, 2]; opened without the data: "
                               "step 1 loaded in ")
    path = tmp_path / "ex" / "cameras.yml"
    views = load_views(path)
    assert list(views) == ["start", "approach_0000", "approach_0047"]
    assert load_tracks(path, views)["approach"].frames == 48
    assert (tmp_path / "ex" / "editor.png").is_file()
