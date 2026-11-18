"""stations: one shot rendered at several stations of a long body, tile by tile."""
import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel import compose
from flowreel.compose import from_dict
from flowreel.scene.errors import ConfigError

from test_plt_window import case  # noqa: F401  (the fixture: a channel 100 long, its floor)

CAMERAS = {"views": [{"name": "side", "position": [0, 0, 30], "focal": [0, 0, 0],
                      "up": [0, 1, 0], "view_angle": 30}]}


def write_shot(folder, crop=True, camera=None):
    shot = {"name": "win", "source": {"adapter": "flexflow", "path": "."},
            "time": {"steps": [1, 2]}, "size": [64, 48],
            "camera": camera or {"view": "side", "follow": "floor"},
            "layers": [{"type": "outline", "bounds": "crop", "colour": "#ffffff", "width": 2}]}
    if crop:
        shot["crop"] = {"around": {"body": "floor", "station": 50}, "half": [5, 2, 2]}
    (folder / "win.yml").write_text(yaml.safe_dump(shot))
    (folder / "cameras.yml").write_text(yaml.safe_dump(CAMERAS))


def stations(folder, picture=(120, 40), **extra):
    spec = {"size": list(picture), "tiles": [{"stations": {"shot": "win.yml", "at": [20, 50, 80]},
                                          "at": [0, 0], "size": [120, 40], **extra}]}
    return from_dict(spec, file=str(folder / "row.yml"))


def test_one_tile_per_station(case):  # noqa: F811
    write_shot(case)
    lay = stations(case, label="x = {station:g}")
    assert [t.station for t in lay.tiles] == [20, 50, 80]
    assert [(t.at, t.size) for t in lay.tiles] == [((0, 0), (40, 40)), ((40, 0), (40, 40)),
                                                    ((80, 0), (40, 40))]
    assert [t.label.text for t in lay.tiles] == ["x = 20", "x = 50", "x = 80"]
    assert [t.shot.name for t in lay.tiles] == ["win_station20", "win_station50", "win_station80"]
    assert [t.shot.crop.station.at(0) for t in lay.tiles] == [20, 50, 80]
    assert all(t.entry == 0 and t.frames is None for t in lay.tiles)


def test_default_labels_a_column_and_no_labels(case):  # noqa: F811
    write_shot(case)
    lay = stations(case, picture=(40, 120), along="column", size=[40, 120])
    assert [t.at for t in lay.tiles] == [(0, 0), (0, 40), (0, 80)]
    assert lay.tiles[0].label.text == "station 20"
    assert all(t.label is None for t in stations(case, label=None).tiles)


def test_a_camera_station_is_moved(case):  # noqa: F811
    write_shot(case, crop=False, camera={"view": "side", "follow": "floor", "station": 10})
    assert [t.shot.camera["station"] for t in stations(case).tiles] == [20, 50, 80]


def test_stations_in_a_grid(case):  # noqa: F811
    write_shot(case)
    lay = from_dict({"size": [80, 80], "grid": [2, 2],
                     "tiles": [{"frames": "other"},
                               {"stations": {"shot": "win.yml", "at": [20, 50, 80]}}]},
                    file=str(case / "g.yml"))
    assert [t.at for t in lay.tiles] == [(0, 0), (40, 0), (0, 40), (40, 40)]
    assert [t.entry for t in lay.tiles] == [0, 1, 1, 1]


def test_each_station_renders_its_window(case):  # noqa: F811
    write_shot(case)
    rep = compose.layout(stations(case, label=None), case / "frames",
                         render={"processes": False, "check_memory": False})
    assert rep.count("composed") == 2
    assert (case / "frames" / "win_station50@40x40" / "frame_00001.png").exists()
    p = np.asarray(Image.open(rep.folder / "frame_00000.png").convert("RGB"))
    # the camera follows the floor at each station, so the three windows look alike
    a, b, c = p[:, :40], p[:, 40:80], p[:, 80:]
    assert a.max() > 0 and np.abs(a.astype(int) - b).mean() < 2 and np.abs(b.astype(int) - c).mean() < 2
    again = compose.layout(stations(case, label=None), case / "frames",
                           render={"processes": False, "check_memory": False})
    assert again.count("skipped") == 2


@pytest.mark.parametrize("extra, msg", [
    ({"stations": {"shot": "win.yml"}}, r"tiles\[0\]\.stations: missing key 'at'"),
    ({"stations": {"shot": "nope.yml", "at": [1]}}, r"tiles\[0\]\.stations\.shot: no shot file"),
    ({"stations": {"shot": "win.yml", "at": ["a"]}}, r"tiles\[0\]\.stations\.at\[0\]: expected a number"),
    ({"frames": "a"}, r"tiles\[0\]: give one of 'frames'"),
    ({"label": "{x}"}, r"tiles\[0\]\.label: cannot format"),
])
def test_errors(case, extra, msg):  # noqa: F811
    write_shot(case)
    spec = {"stations": {"shot": "win.yml", "at": [20]}, "at": [0, 0], "size": [40, 40]}
    spec.update(extra)
    with pytest.raises(ConfigError, match=msg):
        from_dict({"size": [120, 40], "tiles": [spec]}, file=str(case / "row.yml"))


def test_a_shot_that_does_not_move_with_a_station(case):  # noqa: F811
    write_shot(case, crop=False, camera={"view": "side"})
    with pytest.raises(ConfigError, match=r"tiles\[0\]\.stations\.at\[0\]: shot 'win' neither crops"):
        stations(case)
