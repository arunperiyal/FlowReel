"""examples/anchored_caption/run.py: a panning shot rendered, a text and an arrow that follow it."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "anchored_caption" / "run.py"


def white(path):
    """The centroid of the pure white pixels (the text and the arrow), and their count."""
    picture = np.asarray(Image.open(path).convert("RGB")).astype(int)
    ys, xs = np.nonzero(picture.min(axis=2) >= 250)
    return (xs.mean(), ys.mean()), len(xs)


def test_example_builds_a_film_whose_text_follows_the_body(tmp_path):
    need_ffmpeg()
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    if done.returncode != 0 and "render" in done.stderr.lower() and "egl" in done.stderr.lower():
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == ["24 rendered, 0 skipped", "built film.mp4",
                                        "3 stills of pan -> frames/scenes/pan"]
    stills = tmp_path / "ex" / "frames" / "scenes" / "pan"
    (x0, y0), n0 = white(stills / "at_0.30.png")
    (x1, y1), n1 = white(stills / "at_1.00.png")
    assert n0 > 100 and n1 > 100
    assert abs(x0 - x1) + abs(y0 - y1) > 5                  # the text moves with the camera
    assert all(0 < x < 640 and 0 < y < 260 for x, y in ((x0, y0), (x1, y1)))   # in frame, near the sphere
    again = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")],
                           capture_output=True, text=True, timeout=600)
    assert again.stdout.splitlines()[0] == "0 rendered, 24 skipped"
