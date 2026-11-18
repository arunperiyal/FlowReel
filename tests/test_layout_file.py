"""The layout file: schema, defaults and errors that name the file and key path."""
from pathlib import Path

import pytest

from flowreel.compose import Label, from_dict, load
from flowreel.scene.errors import ConfigError

TWO = {"size": [1920, 1080],
       "tiles": [{"frames": "frames/bare", "at": [0, 0], "size": [1280, 540], "label": "bare"},
                 {"frames": "frames/helical", "at": [0, 540], "size": [1280, 540],
                  "fit": "cover", "label": {"text": "helical", "corner": "lower_right",
                                            "size": 20, "colour": "#ffcc00"}}]}


def test_two_tiles():
    lay = from_dict(TWO, file="films/compare.yml")
    assert lay.name == "compare" and lay.size == (1920, 1080) and lay.background == "black"
    a, b = lay.tiles
    assert a.frames == Path("films/frames/bare")          # beside the layout file
    assert a.at == (0, 0) and a.size == (1280, 540) and a.fit == "contain"
    assert a.label == Label("bare")
    assert b.fit == "cover" and b.label == Label("helical", "lower_right", 20.0, "#ffcc00")


def test_load_reads_the_file(tmp_path):
    f = tmp_path / "wake.yml"
    f.write_text("name: wakes\nbackground: '#101010'\ntiles:\n"
                 "  - {frames: a, at: [0, 0], size: [10, 10]}\n")
    lay = load(f)
    assert lay.name == "wakes" and lay.background == "#101010"
    assert lay.tiles[0].frames == tmp_path / "a"


def test_yaml_error_names_the_file(tmp_path):
    f = tmp_path / "bad.yml"
    f.write_text("tiles: [\n")
    with pytest.raises(ConfigError, match=r"bad\.yml: line"):
        load(f)


def tile(**kw):
    return {"frames": "a", "at": [0, 0], "size": [100, 100], **kw}


@pytest.mark.parametrize("data, msg", [
    ({}, r"x\.yml: missing key 'tiles'"),
    ({"tiles": []}, r"tiles: expected at least 1 entries"),
    ({"tiles": [tile()], "sise": [1, 1]}, r"sise: unknown key .*did you mean 'size'"),
    ({"tiles": [{"frames": "a", "at": [0, 0]}]}, r"tiles\[0\]: missing key 'size'"),
    ({"tiles": [tile(at=[0, -1])]}, r"tiles\[0\]\.at\[1\]: must be at least 0"),
    ({"tiles": [tile(size=[100])]}, r"tiles\[0\]\.size: expected two whole numbers"),
    ({"tiles": [tile(fit="fill")]}, r"tiles\[0\]\.fit: 'fill' is not allowed"),
    ({"tiles": [tile(label={"text": "a", "corner": "top"})]}, r"tiles\[0\]\.label\.corner"),
    ({"tiles": [tile(label={"text": "a", "size": 0})]}, r"tiles\[0\]\.label\.size: must be positive"),
    ({"tiles": [tile()], "background": "blak"}, r"background: expected a colour"),
    ({"size": [200, 100], "tiles": [tile(at=[150, 0])]}, r"tiles\[0\]: the tile .* runs past"),
])
def test_errors(data, msg):
    with pytest.raises(ConfigError, match=msg):
        from_dict(data, file="x.yml")
