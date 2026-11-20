"""examples/film_captions/run.py: captions, shapes and a watermark drawn from files."""
import subprocess
import sys
from pathlib import Path

from PIL import Image

RUN = Path(__file__).parent.parent / "examples" / "film_captions" / "run.py"


def test_example_draws_every_caption(tmp_path):
    out = tmp_path / "ex"
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert [line.split()[0] for line in lines[:4]] == ["wake", "title", "groove", "marks"]
    assert lines[2] == "groove  text from (1080, 200) to (1512, 304)"   # place [1080, 200]
    for name in ("wake", "title", "groove", "marks"):
        image = Image.open(out / f"caption_{name}.png")
        assert image.size == (1920, 1080) and image.mode == "RGBA"
    assert Image.open(out / "still.png").size == (1920, 1080)
