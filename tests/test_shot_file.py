import pytest

from flowreel.scene import layers as L
from flowreel.scene import shot as S
from flowreel.scene.errors import ConfigError


@pytest.fixture(autouse=True)
def _layer():
    if "dummy" not in L.available():
        @L.register
        class Dummy(L.Layer):
            name = "dummy"
            options = (L.Option("opacity", "number", default=1.0),)


def shot(**over):
    d = {"name": "s", "source": "run", "time": {"frozen": 5},
         "layers": [{"type": "dummy"}]}
    d.update(over)
    return d


def test_minimal_shot_gets_defaults():
    s = S.from_dict(shot())
    assert s.size == (1920, 1080) and s.antialias == "ssaa" and s.crop is None
    assert s.source == ("tag", "run") and s.background == "black"


def test_full_shot():
    s = S.from_dict(shot(size=[640, 360], crop={"x": [-1, 13], "y": [-6, 6], "z": [-2, 25]},
                         antialias="none", camera={"view": "main"}, background="#101010"))
    assert s.size == (640, 360) and s.crop.lo == (-1, -6, -2) and s.crop.hi == (13, 6, 25)
    assert s.camera == {"view": "main"}


@pytest.mark.parametrize("over, msg", [
    ({"antialias": "ssa"}, r"antialias: .*did you mean 'ssaa'"),
    ({"size": [640]}, r"size: expected \[width, height\]"),
    ({"size": [640, 0]}, r"size\[1\]: must be at least 1"),
    ({"source": "run.pvd"}, r"source: expected a tag \(bare\)"),
    ({"crop": {"x": [3, 1], "y": [0, 1], "z": [0, 1]}}, r"crop.x: .*low < high"),
    ({"crop": {"x": [0, 1]}}, r"crop: missing key 'y'"),
    ({"layers": []}, r"layers: expected at least 1"),
    ({"layers": [{"type": "dummmy"}]}, r"layers\[0\].type: .*did you mean 'dummy'"),
    ({"layers": [{"type": "dummy", "opacty": 1}]}, r"layers\[0\].opacty: unknown key.*opacity"),
    ({"layers": [{"type": "dummy", "opacity": {"keys": 3}}]}, r"layers\[0\].opacity: "),
    ({"nmae": "x"}, r"nmae: unknown key.*did you mean 'name'"),
])
def test_errors(over, msg):
    with pytest.raises(ConfigError, match=msg):
        S.from_dict(shot(**over), file="a.yml")


def test_missing_required():
    d = shot()
    del d["time"]
    with pytest.raises(ConfigError, match="missing key 'time'"):
        S.from_dict(d)


def test_load_names_file_and_syntax_line(tmp_path):
    p = tmp_path / "bad.yml"
    p.write_text("name: ok\nsource: [unclosed\n")
    with pytest.raises(ConfigError, match="bad.yml: "):
        S.load(p)
    p.write_text("name: s\nsource: a\ntime: {frozen: 1}\nlayers: [{type: dummy}]\n")
    assert S.load(p).file == str(p)
