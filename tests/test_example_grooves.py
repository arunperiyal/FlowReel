"""examples/grooves: staggered spanwise grooves, carved, drawn at a small size."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from flowreel.scene.shot import load

HERE = Path(__file__).parent.parent / "examples" / "grooves"


def test_shot_carves_staggered_spanwise_grooves():
    params = load(HERE / "shot.yml").layers[0].values(150)["params"]
    assert params["turns"] == 0 and params["stagger"] == 0.5
    assert params["cut_front"] == pytest.approx(12.3)


def test_example_draws_three_frames(tmp_path):
    out = tmp_path / "grooves.png"
    done = subprocess.run([sys.executable, str(HERE / "run.py"), str(out)],
                          capture_output=True, text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    assert "frames 80, 160, 191" in done.stdout and Image.open(out).size == (1440, 270)
