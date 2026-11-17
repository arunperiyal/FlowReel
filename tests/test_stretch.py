"""stretch: the model drawn scaled along an axis, the frame saying so."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.errors import ConfigError
from flowreel.scene.keys import frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict, stretch_note
from flowreel.scene.views import parse_view

from test_layer_supports import Riser          # a riser 40 D long along x

VIEWS = {"v": parse_view({"name": "v", "position": [2, 0, 40], "focal": [2, 0, 0]})}


def shot(stretch=None, camera=None):
    spec = {"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
            "camera": camera or {"view": "v"}, "size": [320, 180], "antialias": "none",
            "layers": [{"type": "body", "colour": "#ffffff"}]}
    if stretch is not None:
        spec["stretch"] = stretch
    return from_dict(spec, file="nowhere/s.yml")


def test_parsing_and_the_note():
    st = shot({"x": 0.1}).stretch
    assert st.scale == (0.1, 1.0, 1.0) and st.note == "x drawn at 1/10 of its length"
    assert stretch_note((0.05, 2.0, 1.0)) == ("x drawn at 1/20 of its length; "
                                              "y drawn at 2 times its length")
    assert shot({"x": 0.1, "note": False}).stretch.note is None
    assert shot({"x": 0.1, "note": "span 1:10"}).stretch.note == "span 1:10"


@pytest.mark.parametrize("spec, msg", [
    ({"x": 0}, r"stretch\.x: must be positive"),
    ({}, r"stretch: give the factor of at least one axis"),
    ({"x": 0.1, "corner": "top"}, r"stretch\.corner: 'top' is not allowed"),
    ({"x": 0.1, "colour": "red-ish"}, r"stretch\.colour: expected a colour"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        shot(spec)


def white_columns(img):
    cols = np.flatnonzero(((img > 200).all(axis=2)).any(axis=0))
    return cols.min(), cols.max()


def test_the_body_is_drawn_compressed_with_its_note():
    try:
        plain = Scene.make(shot(), Riser(), VIEWS).draw(0)
        squeezed = Scene.make(shot({"x": 0.1, "colour": "#ff0000", "size": 12}),
                              Riser(), VIEWS).draw(0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    a, b = white_columns(plain)
    c, d = white_columns(squeezed)
    assert b == 319 and 20 < (d - c) < 60                  # 40 long runs off; 4 long whole
    red = (squeezed[:, :, 0] > 150) & (squeezed[:, :, 1] < 80)
    rows, cols = np.nonzero(red)
    assert red.sum() > 50 and rows.min() > 155 and cols.min() < 10    # the note, lower left
    assert rows.max() - rows.min() < 16                                # about 12 px high


def test_fit_and_follow_use_the_drawn_positions():
    sc = Scene.make(shot({"x": 0.1}, {"view": "v", "follow": "cyl", "station": 20.0, "axis": "x"}),
                    Riser(), VIEWS)
    assert sc.camera.view(0, sc.data(0)).focal == pytest.approx((2.0, 1.0, 0.0), abs=0.02)


def test_the_stretch_is_in_the_key():
    a = frame_key(Scene.make(shot({"x": 0.1}), Riser(), VIEWS), 0)
    b = frame_key(Scene.make(shot({"x": 0.2}), Riser(), VIEWS), 0)
    assert a != b
