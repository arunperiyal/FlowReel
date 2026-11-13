"""Golden frame: FlowReel's reveal picture against the prototype's, from the same data.

``tests/data/reveal/golden.png`` was drawn by the prototype's own functions
(``tools/make_reveal_data.py``) from the small vtk data next to it. The pictures are
compared with a tolerance, because anti-aliasing and float round-off differ by a few
grey levels on a few edge pixels between runs, drivers and VTK versions (docs/PLAN.md,
Section 21). Measured when written: 0.02% of pixels differ at all, the largest by 13.
"""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.reveal import render_shot

SHOT = Path(__file__).parent / "data" / "reveal" / "shot.yml"
MEAN_LIMIT = 0.5        # mean absolute difference, grey levels of 255
CLEAR_LEVEL = 32        # a pixel "clearly differs" above this
CLEAR_LIMIT = 0.002     # fraction of pixels allowed to differ clearly


def difference(a, b):
    """Mean absolute difference and the fraction of clearly different pixels."""
    d = np.abs(a.astype(int) - b.astype(int))
    return d.mean(), (d.max(axis=2) > CLEAR_LEVEL).mean()


def draw(frame=None):
    try:
        return render_shot(SHOT, frame)
    except (RuntimeError, OSError) as error:        # no OpenGL on this machine
        pytest.skip(f"off-screen rendering is not available: {error}")


@pytest.fixture(scope="module")
def golden():
    return np.asarray(Image.open(SHOT.parent / "golden.png").convert("RGB"))


def test_reveal_frame_matches_the_prototype(golden):
    picture = draw()
    assert picture.shape == golden.shape == (360, 640, 3)
    mean, clear = difference(picture, golden)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


def test_the_comparison_tells_frames_apart(golden):
    """Two frames earlier in the sweep must fail the same limits, or they prove nothing."""
    mean, clear = difference(draw(frame=14), golden)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (mean, clear)


def test_before_the_sweep_the_wake_is_whole_and_coloured(golden):
    picture = draw(frame=0)
    lit = picture.max(axis=2) > 40
    assert lit.sum() > (golden.max(axis=2) > 40).sum()      # nothing cut away yet
