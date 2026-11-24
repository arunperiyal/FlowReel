"""examples/text_boxes/run.py: text, a logo, a divider and shapes drawn as boxes of a scene."""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RUN = Path(__file__).parent.parent / "examples" / "text_boxes" / "run.py"


def test_example_draws_the_boxes(tmp_path):
    out = tmp_path / "ex"
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == ["1 stills of text_boxes -> frames/scenes/text_boxes"]
    still = Image.open(out / "frames" / "scenes" / "text_boxes" / "at_0.50.png").convert("RGB")
    assert still.size == (1920, 1080)
    pixels = np.asarray(still).astype(int)
    assert pixels[130:150, 880:1040].reshape(-1, 3).mean(axis=0)[0] > 150     # the logo's bar
    assert pixels[560:570, 255:265].std() > 5 or pixels[558:562, 160:360].max() > 200   # the circle
