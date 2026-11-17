import runpy
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).parent.parent / "examples" / "flow_layers"


def test_example_draws_something():
    from flowreel.scene.draw import draw_frame
    from flowreel.scene.shot import load
    vortex = runpy.run_path(str(EXAMPLE / "run.py"))["Vortex"]
    try:
        picture = draw_frame(load(EXAMPLE / "shot.yml"), vortex(), 12)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert picture.shape == (360, 640, 3) and (picture.max(axis=2) > 40).mean() > 0.05
