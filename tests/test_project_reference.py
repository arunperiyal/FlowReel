"""Reference values in flowreel.yml (Phase 8, branch 6): given once, taken by every shot
layer and panel whose field needs them, and by the axes' unit."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from flowreel.project import load_project
from flowreel.scene import layers as L
from flowreel.scene.errors import ConfigError
from flowreel.scene.keys import frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from tests.conftest import ToySource
from tests.test_render import VIEWS

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


def project(folder, reference):
    (folder / "flowreel.yml").write_text(yaml.safe_dump({"reference": reference}))
    return folder


def test_the_values_are_read_and_checked(tmp_path):
    assert load_project(project(tmp_path, {"rho": 1000, "u_inf": 0.5})).reference == \
        {"rho": 1000.0, "u_inf": 0.5}
    assert load_project(project(tmp_path, None)).reference == {}
    for bad, message in [({"rho": -1}, "must be positive"), ({"rhoo": 1}, "did you mean 'rho'"),
                         ({"u_inf": "fast"}, "u_inf")]:
        with pytest.raises(ConfigError, match=message):
            load_project(project(tmp_path, bad))


def shot(folder, layer):
    spec = {"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [64, 48], "antialias": "none",
            "layers": [layer]}
    return from_dict(spec, file=str(folder / "toy.yml"))


CP = {"type": "slice", "normal": "z", "position": 0.5, "field": "pressure_coefficient",
      "range": [-1, 1]}


def test_a_shot_layer_takes_the_projects_values(tmp_path):
    project(tmp_path, {"rho": 2.0, "u_inf": 1.0, "length": 0.5})
    scene = Scene.make(shot(tmp_path, CP), ToySource(), VIEWS)
    data = scene.data(0)
    layer = scene.shot.layers[0]
    cut = layer.mesh(L.Frame(0, 0, 0.0, data, layer.values(0)), layer.values(0))
    p = np.asarray(data.flow.point_data["p"])
    assert np.allclose(data.flow.point_data["pressure_coefficient"], p / (0.5 * 2.0 * 1.0**2))
    assert cut.n_points


def test_without_values_the_field_says_what_it_needs(tmp_path):
    project(tmp_path, {})
    scene = Scene.make(shot(tmp_path, CP), ToySource(), VIEWS)
    with pytest.raises(TypeError, match="needs parameter"):
        scene.data(0).need("pressure_coefficient")


def test_the_values_are_in_the_frames_key(tmp_path):
    project(tmp_path, {"rho": 2.0, "u_inf": 1.0})
    a = frame_key(Scene.make(shot(tmp_path, CP), ToySource(), VIEWS), 0)
    project(tmp_path, {"rho": 4.0, "u_inf": 1.0})
    b = frame_key(Scene.make(shot(tmp_path, CP), ToySource(), VIEWS), 0)
    assert a != b


def test_the_axes_take_the_reference_length(tmp_path):
    project(tmp_path, {"length": 0.25})
    layer = {"type": "axes", "style": "ruled", "bounds": {"x": [-1, 1], "y": [-1, 1], "z": [0, 1]},
             "unit": "diameters"}
    scene = Scene.make(shot(tmp_path, layer), ToySource(), VIEWS)
    axes = scene.shot.layers[0]
    assert axes.diameter(scene.data(0)) == 0.25


def test_a_panel_takes_the_values_and_its_own_win(tmp_path):
    from flowreel.compose.panel_file import from_dict as panel_from_dict
    from flowreel.compose.panels import make
    folder = case.write_case(tmp_path)
    data = yaml.safe_load((folder / "flowreel.yml").read_text()) if (folder / "flowreel.yml").exists() else {}
    data = data or {}
    data["reference"] = {"rho": 1000.0, "u_inf": 2.0, "length": 1.0}
    (folder / "flowreel.yml").write_text(yaml.safe_dump(data))
    base = {"type": "section", "size": [480, 270], "times": [0.0],
            "source": {"adapter": "flexflow", "path": "case", "cache": None},
            "body": "cylinder", "station": 2.0, "field": "pressure_coefficient",
            "range": [-2, 2]}
    kind = make(panel_from_dict(base, file=str(folder / "section.yml")))
    assert kind.params == {"rho": 1000.0, "u_inf": 2.0}
    own = make(panel_from_dict({**base, "params": {"rho": 1.0}}, file=str(folder / "section.yml")))
    assert own.params == {"rho": 1.0, "u_inf": 2.0}
    vort = make(panel_from_dict({**base, "field": "vorticity_x"}, file=str(folder / "section.yml")))
    assert vort.params == {}
