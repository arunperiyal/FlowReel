"""A tag's units (data/<tag>/domain.yml): given once, taken by every shot layer and panel
whose field needs them, and by the axes' unit."""
import sys
from pathlib import Path

import numpy as np
import pytest

from flowreel.project.domain import load_domain
from flowreel.project.names import DeclaredSource
from flowreel.scene import layers as L
from flowreel.scene.errors import ConfigError
from flowreel.scene.keys import frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from tag_fixture import tag_project
from tests.conftest import ToySource
from tests.test_render import VIEWS

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


def source(units):
    """The toy source as a tag with ``units`` gives it."""
    opened = DeclaredSource(ToySource(), {})
    opened.units = dict(units)
    return opened


def test_the_values_are_read_and_checked(tmp_path):
    folder = tag_project(tmp_path, "c", units={"rho": 1000, "u_inf": 0.5}) / "data" / "c"
    assert load_domain(folder).units == {"rho": 1000.0, "u_inf": 0.5}
    for bad, message in [({"rho": -1}, "must be positive"), ({"rhoo": 1}, "did you mean 'rho'"),
                         ({"u_inf": "fast"}, "u_inf")]:
        folder = tag_project(tmp_path / "bad", "c", units=bad) / "data" / "c"
        with pytest.raises(ConfigError, match=message):
            load_domain(folder)


def shot(folder, layer):
    spec = {"name": "toy", "source": "toy", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [64, 48], "antialias": "none",
            "layers": [layer]}
    return from_dict(spec, file=str(folder / "toy.yml"))


CP = {"type": "slice", "normal": "z", "position": 0.5, "field": "pressure_coefficient",
      "range": [-1, 1]}


def test_a_shot_layer_takes_the_tags_units(tmp_path):
    scene = Scene.make(shot(tmp_path, CP), source({"rho": 2.0, "u_inf": 1.0, "length": 0.5}), VIEWS)
    data = scene.data(0)
    layer = scene.shot.layers[0]
    cut = layer.mesh(L.Frame(0, 0, 0.0, data, layer.values(0)), layer.values(0))
    p = np.asarray(data.flow.point_data["p"])
    assert np.allclose(data.flow.point_data["pressure_coefficient"], p / (0.5 * 2.0 * 1.0**2))
    assert cut.n_points


def test_without_values_the_field_says_what_it_needs(tmp_path):
    scene = Scene.make(shot(tmp_path, CP), source({}), VIEWS)
    with pytest.raises(TypeError, match="needs parameter"):
        scene.data(0).need("pressure_coefficient")


def test_the_values_are_in_the_frames_key(tmp_path):
    def key(units):
        tag_project(tmp_path, "toy", units=units)
        return frame_key(Scene.make(shot(tmp_path, CP), source(units), VIEWS), 0)
    assert key({"rho": 2.0, "u_inf": 1.0}) != key({"rho": 4.0, "u_inf": 1.0})
    a = frame_key(Scene.make(shot(tmp_path / "x", CP), source({"rho": 2.0}), VIEWS), 0)
    b = frame_key(Scene.make(shot(tmp_path / "x", CP), source({"rho": 4.0}), VIEWS), 0)
    assert a != b                                    # also for a source given with its shot


def test_the_axes_take_the_tags_length(tmp_path):
    layer = {"type": "axes", "style": "ruled", "bounds": {"x": [-1, 1], "y": [-1, 1], "z": [0, 1]},
             "unit": "diameters"}
    scene = Scene.make(shot(tmp_path, layer), source({"length": 0.25}), VIEWS)
    axes = scene.shot.layers[0]
    assert axes.diameter(scene.data(0)) == 0.25


def test_a_panel_takes_the_values_and_its_own_win(tmp_path):
    from flowreel.compose.panel_file import from_dict as panel_from_dict
    from flowreel.compose.panels import make
    domain = case.make_project(tmp_path)            # the tag cylinder, rho 1, u_inf 1
    domain.write_text(domain.read_text().replace("rho: 1.0", "rho: 1000.0").replace("u_inf: 1.0", "u_inf: 2.0"))
    base = {"type": "section", "size": [480, 270], "times": [0.0],
            "source": {"tag": "cylinder", "cache": None},
            "body": "cylinder", "station": 2.0, "field": "pressure_coefficient",
            "range": [-2, 2]}
    folder = tmp_path
    kind = make(panel_from_dict(base, file=str(folder / "section.yml")))
    assert kind.params == {"rho": 1000.0, "u_inf": 2.0}
    own = make(panel_from_dict({**base, "params": {"rho": 1.0}}, file=str(folder / "section.yml")))
    assert own.params == {"rho": 1.0, "u_inf": 2.0}
    vort = make(panel_from_dict({**base, "field": "vorticity_x"}, file=str(folder / "section.yml")))
    assert vort.params == {}
