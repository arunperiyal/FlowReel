"""The contour layer: lines of a field at chosen values on a plane (Phase 8, branch 4)."""
import numpy as np
import pytest

import flowreel.scene.flow_layers  # noqa: F401
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker, ConfigError
from tests.conftest import ToySource


def make(**spec):
    base = {"type": "contour", "normal": "z", "position": 0.5, "field": "speed",
            "range": [0, 1]}
    return L.build({**base, **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, index=0):
    src = ToySource()
    return L.Frame(index, 0, 0.0, L.FrameData(src, 0, src.flow(0, ["U", "V", "W"], None)),
                   layer.values(index))


def lines_of(**spec):
    layer = make(**spec)
    f = frame_for(layer)
    return layer.mesh(f, f.values)


def test_lines_lie_on_the_plane_at_the_values_asked():
    lines = lines_of(levels=[0.2, 0.4])
    assert lines.n_lines > 0 and np.allclose(lines.points[:, 2], 0.5)
    speed = np.asarray(lines["speed"])
    assert np.all(np.isclose(speed, 0.2, atol=1e-6) | np.isclose(speed, 0.4, atol=1e-6))
    assert np.isclose(speed, 0.2, atol=1e-6).any() and np.isclose(speed, 0.4, atol=1e-6).any()


def test_a_count_spreads_levels_over_the_range_and_sweeps_with_it():
    layer = make(levels=5, range={"from": [0, 1], "to": [0, 0.5], "frames": [0, 10],
                                  "ease": "linear"})
    assert layer.level_values(layer.values(0)) == pytest.approx([0, 0.25, 0.5, 0.75, 1])
    assert layer.level_values(layer.values(10)) == pytest.approx([0, 0.125, 0.25, 0.375, 0.5])
    assert layer.key_fields(0) != layer.key_fields(10)


def test_no_level_on_the_plane_draws_nothing():
    assert lines_of(levels=[50.0]) is None


@pytest.mark.parametrize("spec, message", [
    ({"levels": 0}, "at least 1"),
    ({"levels": []}, "at least one value"),
    ({"levels": "many"}, "a list of values or a count"),
    ({"levels": [0.1, "x"]}, r"levels\[1\]|levels\.1"),
    ({"normal": "w"}, "normal"),
])
def test_bad_options_name_the_key(spec, message):
    with pytest.raises(ConfigError, match=message):
        make(**spec)


def test_a_frame_draws_the_lines():
    from flowreel.scene.rendering import Scene
    from tests.test_render import VIEWS, toy_shot
    shot = toy_shot(layers=[{"type": "contour", "normal": "z", "position": 0.5,
                             "field": "speed", "levels": [0.2, 0.4], "colour": "#ff0000",
                             "width": 3}])
    try:
        image = Scene.make(shot, ToySource(), VIEWS).draw(0)
    except RuntimeError as exc:                       # no off-screen OpenGL here
        pytest.skip(str(exc))
    red = (image[..., 0] > 150) & (image[..., 1] < 80) & (image[..., 2] < 80)
    assert red.sum() > 20
