"""Panel tiles in a layout: drawn first, then tiled by index like frames."""
import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel import compose
from flowreel.compose import from_dict
from flowreel.scene.errors import ConfigError
from tests.panel_project import project


def frames(folder, n, size=(40, 30)):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", size, "#ff0000").save(folder / f"frame_{i:05d}.png")


def layout_project(tmp_path, n_frames=3, **tile):
    folder = project(tmp_path / "p")
    (folder / "lift.yml").write_text(yaml.safe_dump(
        {"type": "series", "size": [80, 60], "times": [0.0, 1.0, 2.0],
         "lines": [{"body": "bare", "series": "force", "column": "cl"}]}))
    frames(folder / "flow", n_frames)
    lay = from_dict({"size": [120, 60], "tiles": [
        {"frames": "flow", "at": [0, 0], "size": [40, 30]},
        {"panel": "lift.yml", "at": [40, 0], "size": [80, 60], **tile}]},
        file=str(folder / "board.yml"))
    return folder, lay


def test_the_panel_is_drawn_then_tiled(tmp_path):
    folder, lay = layout_project(tmp_path)
    assert lay.tiles[1].panel == (folder / "lift.yml").resolve() and lay.tiles[1].rate == "flow"
    rep = compose.layout(lay, folder / "out", panels={"processes": False})
    assert rep.count("composed") == 3
    drawn = folder / "out" / "lift"
    assert sorted(p.name for p in drawn.glob("frame_*.png")) == \
        [f"frame_{i:05d}.png" for i in range(3)]
    for i in range(3):
        composed = np.asarray(Image.open(rep.folder / f"frame_{i:05d}.png"))
        panel = np.asarray(Image.open(drawn / f"frame_{i:05d}.png"))
        assert (composed[:, 40:] == panel).all()                  # same size: pasted as drawn
        assert (composed[:30, :40] == (255, 0, 0)).all()
    again = compose.layout(lay, folder / "out", panels={"processes": False})
    assert again.count("skipped") == 3


def test_a_panel_redrawn_recomposes_its_frames(tmp_path):
    folder, lay = layout_project(tmp_path)
    compose.layout(lay, folder / "out", panels={"processes": False})
    (folder / "lift.yml").write_text((folder / "lift.yml").read_text()
                                     .replace("size:\n- 80", "size:\n- 81"))
    rep = compose.layout(lay, folder / "out", panels={"processes": False})
    assert rep.count("composed") == 3


def test_the_whole_panel_is_drawn_for_some_frames(tmp_path):
    folder, lay = layout_project(tmp_path)
    rep = compose.layout(lay, folder / "out", frames=[1], panels={"processes": False})
    assert [f[0] for f in rep.frames] == [1]
    assert len(list((folder / "out" / "lift").glob("frame_*.png"))) == 3


def test_a_shorter_panel_is_missing_frames_unless_held(tmp_path):
    folder, lay = layout_project(tmp_path, n_frames=5)
    with pytest.raises(ConfigError, match="no frame 3"):
        compose.layout(lay, folder / "out", panels={"processes": False})


def test_errors(tmp_path):
    folder = project(tmp_path / "p")
    base = {"size": [100, 100]}
    with pytest.raises(ConfigError, match="no panel file"):
        from_dict({**base, "tiles": [{"panel": "x.yml", "at": [0, 0], "size": [10, 10]}]},
                  file=str(folder / "l.yml"))
    with pytest.raises(ConfigError, match="'rate'.*only with 'panel'|only with 'panel'"):
        from_dict({**base, "tiles": [{"frames": "f", "rate": "output", "at": [0, 0],
                                      "size": [10, 10]}]}, file=str(folder / "l.yml"))
    with pytest.raises(ConfigError, match="give one of"):
        from_dict({**base, "tiles": [{"frames": "f", "panel": "x.yml", "at": [0, 0],
                                      "size": [10, 10]}]}, file=str(folder / "l.yml"))
    (folder / "x.yml").write_text("type: series\ntimes: [0]\n")
    with pytest.raises(ConfigError, match="rate"):
        from_dict({**base, "tiles": [{"panel": "x.yml", "rate": "fast", "at": [0, 0],
                                      "size": [10, 10]}]}, file=str(folder / "l.yml"))
