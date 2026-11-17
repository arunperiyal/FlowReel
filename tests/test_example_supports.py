"""examples/supports/run.py draws a sheet of every support symbol."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

RUN = Path(__file__).parent.parent / "examples" / "supports" / "run.py"


def test_example_draws_every_symbol(tmp_path):
    out = tmp_path / "supports.png"
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True,
                          text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    assert "6 symbols" in done.stdout and Image.open(out).size == (1440, 600)
