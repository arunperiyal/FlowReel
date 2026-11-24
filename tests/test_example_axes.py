"""examples/axes: the three styles of the axes layer round the generated cylinder."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from flowreel.scene.shot import load

HERE = Path(__file__).parent.parent / "examples" / "axes"


def test_shot_has_the_three_styles():
    shot = load(HERE / "shots" / "axes.yml")
    assert [layer.raw["style"] for layer in shot.layers[1:]] == ["ruled", "arrows", "triad"]


def test_template_offers_the_axes_layer():
    import yaml

    from flowreel.scene.shot import from_dict
    from flowreel.scene.template import template
    shot = from_dict(yaml.safe_load(template("a", ["axes"])))
    assert shot.layers[0].name == "axes" and shot.layers[0].raw["style"] == "triad"


def test_example_draws_two_frames(tmp_path):
    out = tmp_path / "axes.png"
    done = subprocess.run([sys.executable, str(HERE / "run.py"), str(out)],
                          capture_output=True, text=True, timeout=600)
    if done.returncode and ("OpenGL" in done.stderr or "display" in done.stderr.lower()):
        pytest.skip("off-screen rendering is not available")
    assert done.returncode == 0, done.stderr[-2000:]
    assert "frames 0, 48" in done.stdout and Image.open(out).size == (1920, 540)
