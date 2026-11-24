"""The section panel (compose/flow_panels.py) on the generated cylinder case."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from matplotlib.figure import Figure
from PIL import Image

from flowreel.compose import panel
from flowreel.compose.panel_file import from_dict
from flowreel.compose.panels import make
from flowreel.scene.errors import ConfigError

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

TIMES = [0.0, 0.5, 1.0, 1.5]


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    folder = tmp_path_factory.mktemp("cylinder")
    case.make_project(folder)                   # the case as the tag cylinder, its body held at both ends
    return folder


def section(folder, **spec):
    base = {"type": "section", "size": [480, 270], "times": TIMES,
            "source": {"tag": "cylinder", "cache": None},
            "body": "cylinder", "station": 2.0, "field": "vorticity_x", "range": [-2, 2]}
    return from_dict({**base, **spec}, file=str(folder / "section.yml"))


def test_state_follows_the_moving_body(folder):
    kind = make(section(folder, inset={"offset": [0, 0.6], "half": 0.25}))
    for k, t in enumerate(TIMES):
        s = kind.state(t, k)
        assert s["step"] == 10 * k and s["station"] == 2.0
        assert np.allclose(s["centre"], [case.centre_y(t), 0], atol=1e-6)
        (main, half, _), (small, small_half, _) = s["views"]
        assert np.allclose(main, s["centre"]) and np.allclose(half, [1.5, 1.5])
        assert np.allclose(small, s["centre"] + [0, 0.6]) and np.allclose(small_half, 0.25)
        assert np.allclose(s["cut"].values["vorticity_x"], 2 * case.OMEGA, atol=1e-4)
        assert len(s["curves"]) == 1


def test_crop_is_a_slab_round_both_views(folder):
    kind = make(section(folder, inset={"offset": [0, 0.6], "half": 0.25}, depth=0.6))
    crop = kind.state(1.0, 2)["crop"]
    yc = case.centre_y(1.0)
    grow = 0.05 * 3.0 + 0.6
    assert crop.lo[0] == pytest.approx(1.4) and crop.hi[0] == pytest.approx(2.6)
    assert crop.lo[1] == pytest.approx(yc - 1.5 - grow) and crop.hi[2] == pytest.approx(1.5 + grow)


def test_streamlines_see_the_flow_from_the_body(folder):
    kind = make(section(folder))
    s = kind.state(0.5, 1)
    assert np.allclose(s["body_velocity"], [0, case.SPEED, 0], atol=1e-6)
    centre, half, _ = s["views"][0]
    A, B, va, vb = kind.flow_grid(s["cut"].triangulation(), s, centre, half)
    # what is left is the rotation about the body: (-OMEGA up, OMEGA across) from its centre
    ok = ~np.ma.getmaskarray(va)
    da, db = A[ok] - s["centre"][0], B[ok] - s["centre"][1]
    assert np.allclose(va[ok], -case.OMEGA * db, atol=1e-4)
    assert np.allclose(vb[ok], case.OMEGA * da, atol=1e-4)
    assert np.hypot(da, db).min() >= case.RADIUS - 0.02          # masked inside the body
    still = make(section(folder, streamlines={"relative": False})).state(0.5, 1)
    assert np.allclose(still["body_velocity"], 0)


def test_station_is_a_track_and_times_pick_the_nearest_step(folder):
    kind = make(section(folder, station={"from": 1.0, "to": 3.0, "frames": [0, 2],
                                         "ease": "linear"}))
    assert kind.state(0.2, 1)["station"] == pytest.approx(2.0)
    assert kind.state(0.2, 1)["step"] == 0 and kind.state(0.26, 0)["step"] == 10
    assert kind.state(0.25, 0)["step"] == 0                       # a tie takes the earlier
    assert kind.state(9.0, 0)["step"] == 30


def test_fixed_centre_and_axes(folder):
    kind = make(section(folder, centre=[0, 0], half=[2, 1], axes=["z", "y"], streamlines=False))
    s = kind.state(1.5, 3)
    assert np.allclose(s["views"][0][0], [0, 0]) and np.allclose(s["views"][0][1], [2, 1])
    assert np.allclose(s["centre"], [0, case.centre_y(1.5)], atol=1e-6)     # z across, y up


def test_draws_frames_and_takes_the_source_of_a_shot(folder):
    shot = {"name": "near", "source": {"tag": "cylinder", "cache": None},
            "time": {"steps": [0, 30]}, "camera": {"view": "main"},
            "layers": [{"type": "slice", "normal": "x", "position": 2, "field": "U"}]}
    (folder / "near.yml").write_text(yaml.safe_dump(shot))
    pf = from_dict({"type": "section", "size": [320, 180], "times": {"shot": "near.yml"},
                    "station": 2, "field": "U", "range": [-1.5, 1.5],
                    "inset": {"offset": [0, 0.6], "half": 0.25}},
                   file=str(folder / "from_shot.yml"))
    report = panel(pf, folder / "frames", processes=False)
    assert report.count("drawn") == 4
    picture = np.asarray(Image.open(report.frames[0][1]))
    assert picture.shape == (180, 320, 3) and picture.std() > 10
    again = panel(pf, folder / "frames", processes=False)
    assert again.count("skipped") == 4


def test_errors_name_the_key(folder):
    with pytest.raises(ConfigError, match="station"):
        make(from_dict({"type": "section", "times": TIMES, "source": "cylinder",
                        "field": "U", "range": [0, 1]}, file=str(folder / "a.yml")))
    with pytest.raises(ConfigError, match="'source'"):
        make(from_dict({"type": "section", "times": TIMES, "station": 1, "field": "U",
                        "range": [0, 1]}, file=str(folder / "a.yml")))
    with pytest.raises(ConfigError, match=r"range.*change from frame to frame"):
        make(section(folder, range=None))
    with pytest.raises(ConfigError, match="no field 'vort'"):
        make(section(folder, field="vort"))
    with pytest.raises(ConfigError, match="no body 'pipe'"):
        make(section(folder, body="pipe"))
    with pytest.raises(ConfigError, match=r"axes.*normal"):
        make(section(folder, axes=["x", "y"]))
    with pytest.raises(ConfigError, match=r"inset.*half"):
        make(section(folder, inset={"half": -1}))
    kind = make(section(folder, station=9.0))
    kind.build(Figure())
    with pytest.raises(ConfigError, match=r"time 0.*no points"):
        kind.update(0.0, 0)
