import runpy
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).parent.parent / "examples" / "flow_layers"


def test_example_draws_something():
    from flowreel.scene import render_frame
    from flowreel.scene.shot import load
    vortex = runpy.run_path(str(EXAMPLE / "run.py"))["Vortex"]
    try:
        picture = render_frame(load(EXAMPLE / "shot.yml"), 12, vortex())
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert picture.shape == (360, 640, 3) and (picture.max(axis=2) > 40).mean() > 0.05


def test_marker_example_draws_something():
    from flowreel.scene import render_frame
    from flowreel.scene.shot import load
    from flowreel.sources.geometry import GeometrySource
    folder = EXAMPLE.parent / "marker_layers"
    source = GeometrySource("grooved_cylinder", params={"span": 6, "samples": (41, 81)})
    try:
        picture = render_frame(load(folder / "shot.yml"), 12, source)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert picture.shape == (360, 640, 3) and (picture.max(axis=2) > 40).mean() > 0.02
