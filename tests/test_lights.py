import pytest

from flowreel.scene.errors import ConfigError
from flowreel.scene.lights import KITS, apply_lights, parse_lights
from flowreel.scene.views import View


def test_presets():
    assert parse_lights("default") == KITS["default"]
    r = parse_lights("raking")
    assert r[0].kind == "scene" and r[0].intensity > 5 * r[1].intensity


def test_list_with_defaults():
    (a, b) = parse_lights([{}, {"kind": "scene", "direction": [0, 1, 0], "intensity": 0.5,
                                "colour": "#ff0000"}])
    assert a.kind == "head" and a.intensity == 1.0
    assert b.direction == (0, 1, 0) and b.colour[0] == pytest.approx(1.0)


@pytest.mark.parametrize("spec, msg", [
    ("rakin", "did you mean 'raking'"),
    ([], "at least 1"),
    ([{"kind": "sun"}], r"lights\[0\].kind"),
    ([{"kind": "scene", "direction": [0, 0, 0]}], "non-zero direction"),
    ([{"intensity": -1}], "cannot be negative"),
    ([{"intensty": 1}], "did you mean 'intensity'"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_lights(spec)


def test_apply_to_plotter_counts_lights():
    import pyvista as pv
    pl = pv.Plotter(off_screen=True)
    apply_lights(pl, parse_lights("default"), View((0, 0, 5), (0, 0, 0)))
    assert len(pl.renderer.lights) == 2
    pl.close()
