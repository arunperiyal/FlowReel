"""compose.layout: composed frames, fits, labels, and keys that skip fresh frames."""
import os

import numpy as np
from PIL import Image

from flowreel import compose
from flowreel.compose import from_dict


def frames(folder, colours, size=(40, 20)):
    """frame_0000i.png in ``folder``, one solid colour each."""
    folder.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(colours):
        Image.new("RGB", size, c).save(folder / f"frame_{i:05d}.png")
    return folder


def two(tmp_path, **tile_b):
    frames(tmp_path / "a", ["#ff0000", "#00ff00"])
    frames(tmp_path / "b", ["#0000ff", "#ffffff"])
    return from_dict({"size": [80, 20], "background": "black",
                      "tiles": [{"frames": "a", "at": [0, 0], "size": [40, 20]},
                                {"frames": "b", "at": [40, 0], "size": [40, 20], **tile_b}]},
                     file=str(tmp_path / "pair.yml"))


def pixels(path):
    return np.asarray(Image.open(path).convert("RGB"))


def test_tiles_side_by_side(tmp_path):
    rep = compose.layout(two(tmp_path), tmp_path / "out")
    assert rep.folder == tmp_path / "out" / "pair" and rep.count("composed") == 2
    p0, p1 = (pixels(rep.folder / f"frame_0000{i}.png") for i in (0, 1))
    assert p0.shape == (20, 80, 3)
    assert (p0[:, :40] == (255, 0, 0)).all() and (p0[:, 40:] == (0, 0, 255)).all()
    assert (p1[:, :40] == (0, 255, 0)).all() and (p1[:, 40:] == (255, 255, 255)).all()


def test_contain_cover_and_stretch(tmp_path):
    from flowreel.compose.layout_file import Tile
    from flowreel.compose.tiling import fitted
    half = Image.new("RGB", (20, 20), "#ffffff")          # square frame in a 40 x 20 tile
    contain = np.asarray(fitted(half, Tile("x", (0, 0), (40, 20), "contain")))
    assert (contain[:, 10:30] == 255).all() and (contain[:, :10] == 0).all() and (contain[:, 30:] == 0).all()
    tall = Image.new("RGB", (20, 40), "#ffffff")
    tall.paste(Image.new("RGB", (20, 10), "#ff0000"), (0, 0))   # red top quarter, cut by cover
    cover = np.asarray(fitted(tall, Tile("x", (0, 0), (40, 20), "cover")))
    assert cover.shape == (20, 40, 3) and (cover[2:-2] == 255).all()
    stretch = fitted(tall, Tile("x", (0, 0), (40, 20), "stretch"))
    assert stretch.size == (40, 20)


def test_a_label_is_written_in_its_corner(tmp_path):
    lay = two(tmp_path, label={"text": "B", "corner": "lower_right", "size": 12})
    rep = compose.layout(lay, tmp_path / "out")
    p = pixels(rep.folder / "frame_00000.png")
    tile = p[:, 40:]
    changed = np.argwhere((tile != (0, 0, 255)).any(axis=2))
    assert len(changed) and changed[:, 1].min() >= 20 and changed[:, 0].max() == 13   # lower right, on the baseline
    assert (p[:, :40] == (255, 0, 0)).all()                                          # tile a untouched


def test_fresh_frames_are_skipped(tmp_path):
    lay = two(tmp_path)
    out = tmp_path / "out"
    compose.layout(lay, out)
    assert compose.layout(lay, out).count("skipped") == 2
    assert compose.layout(lay, out, force=True).count("composed") == 2


def test_a_rerendered_tile_frame_is_composed_again(tmp_path):
    lay = two(tmp_path)
    out = tmp_path / "out"
    compose.layout(lay, out)
    f = tmp_path / "b" / "frame_00001.png"
    Image.new("RGB", (40, 20), "#123456").save(f)
    os.utime(f, ns=(f.stat().st_atime_ns, f.stat().st_mtime_ns + 10**9))
    rep = compose.layout(lay, out)
    assert [s for _, _, s in rep.frames] == ["skipped", "composed"]
    assert (pixels(rep.folder / "frame_00001.png")[:, 40:] == (0x12, 0x34, 0x56)).all()


def test_a_changed_layout_is_composed_again(tmp_path):
    out = tmp_path / "out"
    compose.layout(two(tmp_path), out)
    assert compose.layout(two(tmp_path, fit="stretch"), out).count("composed") == 2


def test_some_frames_and_a_draft(tmp_path):
    lay = two(tmp_path)
    rep = compose.layout(lay, tmp_path / "out", frames=[1], scale=0.5)
    assert rep.folder.name == "pair@40x10" and [f[0] for f in rep.frames] == [1]
    p = pixels(rep.folder / "frame_00001.png")
    assert p.shape == (10, 40, 3) and (p[:, :20] == (0, 255, 0)).all()


def test_a_frame_outside_the_tiles(tmp_path):
    import pytest

    from flowreel.scene.errors import ConfigError
    with pytest.raises(ConfigError, match=r"pair\.yml: frame 5 is not in the layout's tiles \(0\.\.1\)"):
        compose.layout(two(tmp_path), tmp_path / "out", frames=[5])
