"""Phase 3's check: the comparison and lift-map frames, composed from files by
``flowreel compose``, match golden frames drawn by the prototype's own code.

Data: the generated cases of ``examples/compare/case_data.py``, written at test time.
Goldens: ``tests/data/compare/golden.png`` (``tools/make_compare_golden.py``, the
prototype's ``compose_compare.py``) and ``tests/data/liftmap/golden.png``
(``tools/make_liftmap_golden.py``, its ``render_extras.py liftmap``). The limits are
those of Phase 2's golden tests. Each also draws a frame near the golden one, which
must fail the same limits, or the check proves nothing.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from cli_harness import Shell
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

HERE = Path(__file__).parent
EXAMPLE = HERE.parent / "examples" / "compare"
sys.path.insert(0, str(EXAMPLE))
import case_data  # noqa: E402

FILES = ("flowreel.yml", "compare.yml", "plots.yml", "liftmap.yml")


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    """The comparison's frames 15 and 13 through ``compose layout``, and the lift map's
    frames 20 and 17 through ``compose panel``."""
    folder = tmp_path_factory.mktemp("compare")
    case_data.write_data(folder)
    for name in FILES:
        shutil.copy(EXAMPLE / name, folder / name)
    sh = Shell(folder / "store")
    status, out, err = sh.run(f"compose layout {folder / 'compare.yml'} --frames 13,15 "
                              f"-o {folder / 'frames'}")
    assert status == 0, err
    status, out, err = sh.run(f"compose panel {folder / 'liftmap.yml'} --frames 17,20 "
                              f"-o {folder / 'frames'}")
    assert status == 0, err

    def read(name, i):
        return np.asarray(Image.open(folder / "frames" / name / f"frame_{i:05d}.png").convert("RGB"))

    return {"compare": {i: read("compare", i) for i in (13, 15)},
            "liftmap": {i: read("liftmap", i) for i in (17, 20)}}


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
