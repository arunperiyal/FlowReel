import pytest

from flowreel.scene.errors import ConfigError
from flowreel.scene.views import load_views, parse_view


def test_defaults_and_direction():
    v = parse_view({"position": [0, 0, 10], "focal": [0, 0, 0]})
    assert v.up == (0, 1, 0) and v.view_angle == 30 and not v.parallel
    assert tuple(v.direction) == (0, 0, -1) and v.distance == 10


def test_parallel_needs_scale():
    with pytest.raises(ConfigError, match="needs 'parallel_scale'"):
        parse_view({"position": [0, 0, 1], "focal": [0, 0, 0], "parallel": True})
    v = parse_view({"position": [0, 0, 1], "focal": [0, 0, 0], "parallel": True, "parallel_scale": 4})
    assert v.parallel and v.parallel_scale == 4


@pytest.mark.parametrize("spec, msg", [
    ({"position": [0, 0, 1], "focal": [0, 0, 1]}, "same point"),
    ({"position": [0, 0, 1], "focal": [0, 0, 0], "up": [0, 0, 1]}, "up: .*parallel"),
    ({"position": [0, 0, 1], "focal": [0, 0, 0], "view_angle": 200}, "view_angle: must be between"),
    ({"position": [0, 0], "focal": [0, 0, 0]}, "position: expected 3 numbers"),
    ({"position": [0, 0, 1], "focal": [0, 0, 0], "veiw_angle": 3}, "did you mean 'view_angle'"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_view(spec)


def test_load_views_and_bare_view(tmp_path):
    p = tmp_path / "cameras.yml"
    p.write_text("views:\n  - {name: a, position: [0,0,5], focal: [0,0,0]}\n"
                 "  - {name: b, position: [5,0,0], focal: [0,0,0], up: [0,0,1]}\n")
    assert list(load_views(p)) == ["a", "b"]
    p.write_text("views:\n  - {name: a, position: [0,0,5], focal: [0,0,0]}\n"
                 "  - {name: a, position: [0,0,6], focal: [0,0,0]}\n")
    with pytest.raises(ConfigError, match=r"views\[1\].name: duplicate"):
        load_views(p)
    p.write_text("{position: [0,0,5], focal: [0,0,0]}\n")
    assert list(load_views(p)) == ["main"]
    p.write_text("views:\n  - {position: [0,0,5], focal: [0,0,0]}\n")
    with pytest.raises(ConfigError, match="missing key 'name'"):
        load_views(p)
