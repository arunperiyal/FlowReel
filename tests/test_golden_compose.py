"""Phase 3's check: the comparison and lift-map frames, drawn as the scenes of
``examples/compare``, match golden frames drawn by the prototype's own code.

Data: the generated cases of ``examples/compare/case_data.py``, written by its run.py.
Goldens: ``tests/data/compare/golden.png`` (``tools/make_compare_golden.py``, the
prototype's ``compose_compare.py``) and ``tests/data/liftmap/golden.png``
(``tools/make_liftmap_golden.py``, its ``render_extras.py liftmap``). The limits are
those of Phase 2's golden tests. Each also draws a frame near the golden one, which
must fail the same limits, or the check proves nothing.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

HERE = Path(__file__).parent
RUN = HERE.parent / "examples" / "compare" / "run.py"       # the project: tags, panels, scenes

#: ``(scene, frame): seconds into the scene`` of the frames compared, four a second: the lift
#: map at exactly the time of its frames 20 and 17 (a frame between two would differ from the
#: golden by the width of the fill's edge), the wakes at frames 15 and 13 (the wakes are
#: interpolated between saved frames either way)
AT = {("compare", 15): 3.9, ("compare", 13): 3.4, ("liftmap", 20): 5.0, ("liftmap", 17): 4.25}


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    """The example's project built, then stills of its scenes at the times of ``AT``."""
    folder = tmp_path_factory.mktemp("compare")
    done = subprocess.run([sys.executable, str(RUN), str(folder)], capture_output=True,
                          text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-2000:]
    out = {"compare": {}, "liftmap": {}}
    for (scene, frame), t in AT.items():
        done = subprocess.run([sys.executable, "-m", "flowreel", "scene", "preview", scene,
                               "--at", str(t)], cwd=folder, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr[-2000:]
        path = folder / "frames" / "scenes" / scene / f"at_{t:.2f}.png"
        out[scene][frame] = np.asarray(Image.open(path).convert("RGB"))
    return out


def golden(name):
    return np.asarray(Image.open(HERE / "data" / name / "golden.png").convert("RGB"))


def test_the_comparison_matches_its_golden_frame(drawn):
    gold = golden("compare")
    picture = drawn["compare"][15]
    assert picture.shape == gold.shape == (1080, 1920, 3)
    mean, clear = difference(picture, gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)
    mean, clear = difference(drawn["compare"][13], gold)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, ("nearby frame", mean, clear)


def test_the_plots_alone_tell_two_frames_apart(drawn):
    """The wakes differ between frames anyway, so the plots are checked on their own.
    Their lines are thin, so a moved line changes the mean little: the share of clearly
    different pixels is what tells the frames apart."""
    gold = golden("compare")[:, 1280:]
    mean, clear = difference(drawn["compare"][15][:, 1280:], gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)
    _, clear = difference(drawn["compare"][13][:, 1280:], gold)
    assert clear > CLEAR_LIMIT, ("nearby plots", clear)


def test_the_lift_map_matches_its_golden_frame(drawn):
    gold = golden("liftmap")
    picture = drawn["liftmap"][20]
    assert picture.shape == gold.shape == (1080, 1920, 3)
    mean, clear = difference(picture, gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)
    mean, clear = difference(drawn["liftmap"][17], gold)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, ("nearby frame", mean, clear)
