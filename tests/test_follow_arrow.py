"""An arrow box that follows a point of the flow lands on it, as the camera pans.

``examples/anchored_caption``'s arrow follows the point just over the sphere's top
(``[0, 0, 0.72]``; the sphere is at ``[0, 0, 0.5]`` with radius 0.2). No prototype drew
this, so there is no golden picture: the check is geometric. The scene is drawn with and
without the arrow; the arrow's pixels are the difference, and its tip must sit at the
sphere's highest pixel in the picture (within 10 pixels), at every time. The scene drawn
again with the point moved far up must fail the same check, or the check proves nothing.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "anchored_caption" / "run.py"
TIMES = (0.3, 1.0, 1.7)
ARROW = re.compile(r"(        - shape: \{kind: arrow.*?\n.*?\n.*?\n)", re.S)


def flowreel(folder, *args):
    done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder,
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]


def stills(folder, film_text):
    """Stills of the scene at ``TIMES`` for a ``film.yml`` text, as arrays."""
    (folder / "film.yml").write_text(film_text)
    flowreel(folder, "scene", "preview", "pan", "--at", *map(str, TIMES))
    return [np.asarray(Image.open(folder / "frames" / "scenes" / "pan" / f"at_{t:.2f}.png")
                       .convert("RGB")).astype(int) for t in TIMES]


def sphere_top(picture):
    """The sphere's highest pixel row and its middle there: grey pixels (the outline is blue)."""
    r, g, b = picture[..., 0], picture[..., 1], picture[..., 2]
    mask = (r > 40) & (abs(r - g) < 8) & (abs(g - b) < 8) & (abs(r - b) < 8)
    ys, xs = np.nonzero(mask)
    top = ys.min()
    return xs[ys <= top + 2].mean(), top


def arrow_tip(with_arrow, without):
    """The arrow's lowest pixel (a ``down_left`` arrow ends at its lower left)."""
    ys, xs = np.nonzero(abs(with_arrow - without).sum(axis=2) > 60)
    assert len(ys) > 50, "no arrow drawn"
    low = ys.max()
    return xs[ys >= low - 1].mean(), low


@pytest.fixture(scope="module")
def pictures(tmp_path_factory):
    need_ffmpeg()
    folder = tmp_path_factory.mktemp("arrow") / "ex"
    done = subprocess.run([sys.executable, str(RUN), str(folder)], capture_output=True,
                          text=True, timeout=900)
    if done.returncode != 0 and "egl" in done.stderr.lower():
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    film = (folder / "film.yml").read_text()
    only_arrow = re.sub(r"        - text: .*?\n.*?\n.*?\n(?=        - shape)", "", film, flags=re.S)
    assert "text:" not in only_arrow.split("boxes:")[1]
    bare = re.sub(r"        - shape: .*", "", only_arrow, flags=re.S)
    moved = only_arrow.replace("[0, 0, 0.72]", "[0, 0, 1.5]")
    return stills(folder, only_arrow), stills(folder, bare), stills(folder, moved)


def test_the_arrow_tip_is_on_the_point_at_every_time(pictures):
    arrow, bare, _ = pictures
    for a, b in zip(arrow, bare):
        tx, ty = arrow_tip(a, b)
        sx, sy = sphere_top(b)
        assert abs(tx - sx) <= 12 and abs(sy - ty) <= 10, ((tx, ty), (sx, sy))


def test_the_arrow_moves_with_the_camera(pictures):
    arrow, bare, _ = pictures
    tips = [arrow_tip(a, b) for a, b in zip(arrow, bare)]
    assert max(abs(tips[0][0] - t[0]) + abs(tips[0][1] - t[1]) for t in tips[1:]) > 5


def test_a_point_moved_far_up_fails_the_check(pictures):
    _, bare, moved = pictures
    tx, ty = arrow_tip(moved[0], bare[0])
    sx, sy = sphere_top(bare[0])
    assert not (abs(tx - sx) <= 12 and abs(sy - ty) <= 10)
