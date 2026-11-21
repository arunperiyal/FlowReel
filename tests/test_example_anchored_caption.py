"""examples/anchored_caption/run.py: a panning shot rendered, a caption that follows it."""
import subprocess
import sys
from pathlib import Path

import pytest

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "anchored_caption" / "run.py"


def test_example_builds_a_film_whose_caption_follows_the_body(tmp_path):
    need_ffmpeg()
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    if done.returncode != 0 and "render" in done.stderr.lower() and "egl" in done.stderr.lower():
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert lines[:2] == ["rendered 24 frames, 0 kept", "built film.mp4"]
    tops = [tuple(int(v) for v in line.split("(")[1].rstrip(")").split(", ")) for line in lines[2:5]]
    assert len(set(tops)) == 3                       # the point moves with the camera
    assert all(0 < x < 640 and 0 < y < 180 for x, y in tops)   # above the centre, in frame
    assert not [line for line in lines if line.startswith("hidden:")]
    again = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")],
                           capture_output=True, text=True, timeout=600)
    assert again.stdout.splitlines()[0] == "rendered 0 frames, 24 kept"
