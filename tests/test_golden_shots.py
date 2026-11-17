"""Phase 2's check: the reveal, domain and carving shots, each rendered from its shot file
by ``flowreel shot render``, match golden frames drawn by the prototype's own code.

Goldens: ``tests/data/reveal/golden.png`` (``tools/make_reveal_data.py``),
``tests/data/domain/golden.png`` (``tools/make_domain_data.py``, render_frozen.py) and
``tests/data/carve/golden.png`` (``tools/make_carve_golden.py``, render_carve.py). The
limits are those of the reveal's golden test: anti-aliasing, float round-off and the
OpenGL driver move a few grey levels on a few edge pixels. Each shot also renders a
frame near the golden one, which must fail the same limits, or the check proves nothing.
"""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from cli_harness import Shell
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

DATA = Path(__file__).parent / "data"
SHOTS = {                     # shot file, golden frame, a nearby frame that must differ
    "reveal": (DATA / "reveal" / "reveal.yml", 16, 13),
    "domain": (DATA / "domain" / "domain.yml", 224, 212),
    "carve": (DATA / "carve" / "carve.yml", 115, 105),
}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Render the golden and nearby frames of every shot once, through the command."""
    out = tmp_path_factory.mktemp("frames")
    sh = Shell(out / "store")
    pictures = {}
    for name, (shot, frame, near) in SHOTS.items():
        status, _, err = sh.run(f"shot render {shot} --frames {frame},{near} -j 2 -o {out}")
        if status and ("OpenGL" in err or "display" in err.lower()):
            pytest.skip(f"off-screen rendering is not available: {err}")
        assert status == 0, err
        pictures[name] = {i: np.asarray(Image.open(out / name / f"frame_{i:05d}.png").convert("RGB"))
                          for i in (frame, near)}
    return pictures


@pytest.mark.parametrize("name", list(SHOTS))
def test_shot_matches_its_golden_frame(name, rendered):
    shot, frame, near = SHOTS[name]
    golden = np.asarray(Image.open(shot.parent / "golden.png").convert("RGB"))
    picture = rendered[name][frame]
    assert picture.shape == golden.shape == (360, 640, 3)
    mean, clear = difference(picture, golden)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (name, mean, clear)
    mean, clear = difference(rendered[name][near], golden)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (name, "nearby frame", mean, clear)
