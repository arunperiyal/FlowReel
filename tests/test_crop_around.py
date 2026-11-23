"""crop: {around: ...}: a window that travels with a body, the camera with it."""
import numpy as np
import pytest

from flowreel.scene.errors import ConfigError
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import CropAround, from_dict
from flowreel.scene.views import parse_view
from flowreel.sources.plt import PltSource

from test_plt_window import NY, NZ, case  # noqa: F401  (the fixture)

VIEWS = {"side": parse_view({"name": "side", "position": [0, 0, 30], "focal": [0, 0, 0]})}


def shot(crop, camera=None):
    spec = {"name": "w", "source": "flexflow:none", "time": {"frozen": 1, "frames": 4},
            "camera": camera or {"view": "side"}, "size": [64, 48], "crop": crop,
            "layers": [{"type": "outline", "bounds": "crop"}]}
    return from_dict(spec, file="nowhere/w.yml")


AROUND = {"around": {"body": "floor", "station": {"from": 20, "to": 80, "frames": [0, 3],
                                                    "ease": "linear"}},
          "half": [5, 2, 2]}


def test_the_crop_travels_with_the_body(case):  # noqa: F811
    sc = Scene.make(shot(AROUND), PltSource(case, cache=None), VIEWS)
    assert isinstance(sc.shot.crop, CropAround)
    for i, station in enumerate((20, 40, 60, 80)):
        box = sc.crop(i)
        # the floor's centre at a station is (station, -1.5, 0)
        assert np.allclose(box.lo, (station - 5, -3.5, -2)) and np.allclose(box.hi, (station + 5, 0.5, 2))
        flow = sc.data(i).flow
        assert flow.n_cells == 40 * 2 * NZ                  # 40 cells of 0.25 along x, 2 rows
        assert flow.bounds[0] >= station - 5 and flow.bounds[1] <= station + 5


def test_the_camera_takes_the_crops_station(case):  # noqa: F811
    sc = Scene.make(shot(AROUND, {"view": "side", "follow": True}),
                    PltSource(case, cache=None), VIEWS)
    for i, station in enumerate((20, 40, 60, 80)):
        assert sc.camera.view(i, sc.data(i)).focal == pytest.approx((station, -1.5, 0), abs=1e-6)


def test_the_key_follows_the_box(case):  # noqa: F811
    from flowreel.scene.keys import frame_parts
    sc = Scene.make(shot(AROUND), PltSource(case, cache=None), VIEWS)
    assert frame_parts(sc, 0)["crop"] != frame_parts(sc, 1)["crop"]


@pytest.mark.parametrize("crop, msg", [
    ({"around": {"body": "floor"}, "half": [1, 1, 1]}, r"crop\.around: missing key 'station'"),
    ({"around": {"station": 3}}, r"crop: missing key 'half'"),
    ({"around": {"station": 3}, "half": [1, 0, 1]}, r"crop\.half: half-sizes must be positive"),
    ({"around": {"station": 3, "at": 1}, "half": [1, 1, 1]}, r"crop\.around\.at: unknown key"),
])
def test_errors(crop, msg):
    with pytest.raises(ConfigError, match=msg):
        shot(crop)


def test_follow_without_station_or_crop():
    with pytest.raises(ConfigError, match="'follow' needs 'station'"):
        from flowreel.scene.camera import shot_camera
        shot_camera(shot(None, {"view": "side", "follow": True}), VIEWS)
