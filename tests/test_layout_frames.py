"""Frames matched by index across tiles; a missing frame is an error unless held."""
import pytest

from flowreel.compose import from_dict
from flowreel.compose.frames import frame_files, match
from flowreel.scene.errors import ConfigError


def layout(missing="error"):
    return from_dict({"size": [20, 10], "grid": [1, 2], "missing": missing,
                      "tiles": [{"frames": "a"}, {"frames": "b"}]}, file="l.yml")


def test_frame_files(tmp_path):
    for name in ("frame_00000.png", "frame_00002.png", "frame_00001.part.png", "notes.txt"):
        (tmp_path / name).write_bytes(b"")
    assert sorted(frame_files(tmp_path)) == [0, 2]
    assert frame_files(tmp_path / "nowhere") == {}


def test_frames_match_by_index():
    m = match(layout(), {0: {0: "a0", 1: "a1"}, 1: {0: "b0", 1: "b1"}})
    assert m.indices == [0, 1]
    assert m.files == {0: ["a0", "b0"], 1: ["a1", "b1"]} and m.held == {}


def test_a_missing_frame_is_an_error():
    with pytest.raises(ConfigError, match=r"l\.yml: tiles\[1\]\.frames: .*has no frame 2 "
                                          r"\(it has 0-1, 4\).*missing: hold"):
        match(layout(), {0: {0: "a0", 1: "a1", 2: "a2", 4: "a4"}, 1: {0: "b0", 1: "b1", 4: "b4"}})


def test_hold_shows_the_nearest_earlier_frame():
    m = match(layout("hold"), {0: {0: "a0", 1: "a1", 2: "a2", 3: "a3"}, 1: {1: "b1", 3: "b3"}})
    assert m.indices == [0, 1, 2, 3]
    assert [m.files[i][1] for i in m.indices] == ["b1", "b1", "b1", "b3"]   # first before it starts
    assert m.held == {0: [1], 2: [1]}


def test_a_tile_without_frames(tmp_path):
    with pytest.raises(ConfigError, match=r"tiles\[0\]\.frames: no frame_NNNNN\.png files"):
        match(from_dict({"tiles": [{"frames": "empty", "at": [0, 0], "size": [1, 1]}]},
                        file=str(tmp_path / "l.yml")))


def test_missing_must_be_error_or_hold():
    with pytest.raises(ConfigError, match=r"missing: 'keep' is not allowed"):
        layout("keep")
