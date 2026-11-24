"""A project's data by tag (Phase 9, branch 1): data/<tag>/domain.yml, its loader, and
sources opened from a tag with its bodies and units."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from flowreel.project import load_project
from flowreel.project import domain as D
from flowreel.scene.errors import ConfigError

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


def tag(root, name, spec):
    folder = root / "data" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "domain.yml").write_text(yaml.safe_dump(spec, sort_keys=False))
    return folder


def plt_tag(root, name, units=None):
    """A tag of the generated cylinder case, its PLT folder linked as plt/."""
    cases = root / "cases" / name
    case.write_case(cases, project=False)
    folder = tag(root, name, {"kind": "plt", "source": {"path": "plt"},
                              "units": units or {"rho": 2.0, "u_inf": 1.0, "mu": 0.5},
                              "bodies": {"cyl": {"zone": "cyl", "axis": "x", "diameter": 1.0}}})
    (folder / "plt").symlink_to((cases / "case").resolve(), target_is_directory=True)
    return folder


@pytest.mark.parametrize("kind", D.KINDS)
def test_the_template_of_each_kind_loads(tmp_path, kind):
    folder = tmp_path / "data" / "t1"
    folder.mkdir(parents=True)
    (folder / "domain.yml").write_text(D.template(kind))
    loaded = D.load_domain(folder)
    assert loaded.tag == "t1" and loaded.kind == kind and loaded.bodies == {}
    assert "units:" in D.template(kind) and "mu:" in D.template(kind)


def test_two_tags_may_name_a_zone_alike(tmp_path):
    """The reason for tags: the AFMS film's two cases both call their wall cyl."""
    (tmp_path / "flowreel.yml").write_text("tags: [bare, helical]\n")
    plt_tag(tmp_path, "bare")
    plt_tag(tmp_path, "helical", units={"rho": 1000.0, "mu": 1.0, "u_inf": 1.0})
    project = load_project(tmp_path)
    assert project.tag_names == ("bare", "helical") and set(project.tags) == {"bare", "helical"}
    sources = {t: D.open_tag(d) for t, d in project.tags.items()}
    for name, source in sources.items():
        assert source.tag == name and "cyl" in source.bodies()
        assert source.body(source.steps()[0], "cyl").n_points
    assert sources["helical"].units["rho"] == 1000.0 and sources["bare"].units["rho"] == 2.0


def test_a_tags_units_reach_the_fields(tmp_path):
    """No params anywhere: the pressure coefficient takes rho and u_inf from the tag."""
    from flowreel.scene.rendering import Scene
    from flowreel.scene.shot import from_dict
    from tests.test_render import VIEWS
    (tmp_path / "flowreel.yml").write_text("")
    domain = D.load_domain(plt_tag(tmp_path, "bare"))
    shot = from_dict({"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
                      "camera": {"view": "main"}, "size": [32, 18],
                      "layers": [{"type": "slice", "normal": "x", "position": 2.0,
                                  "field": "pressure_coefficient", "range": [-1, 1]}]},
                     file=str(tmp_path / "shots" / "s.yml"))
    scene = Scene.make(shot, D.open_tag(domain), VIEWS)
    data = scene.data(0)
    data.need("pressure_coefficient")
    p = np.asarray(data.flow.point_data["p"])
    assert np.allclose(data.flow.point_data["pressure_coefficient"], p / (0.5 * 2.0 * 1.0))
    assert scene.reference["mu"] == 0.5


def test_paths_are_taken_from_the_tags_folder(tmp_path):
    folder = tag(tmp_path, "run", {"kind": "vtk", "source": {
        "path": "vtk/flow.pvd", "body": {"cylinder": "vtk/cylinder.vtp"}}})
    loaded = D.load_domain(folder)
    assert loaded.source["path"] == str(folder / "vtk" / "flow.pvd")
    assert loaded.source["body"] == {"cylinder": str(folder / "vtk" / "cylinder.vtp")}


@pytest.mark.parametrize("name, spec, message", [
    ("bad.name", {"kind": "plt"}, "no dots"),
    ("ok", {"kind": "csv"}, "kind"),
    ("ok", {}, "kind"),
    ("ok", {"kind": "geometry"}, "needs 'body'"),
    ("ok", {"kind": "plt", "units": {"rho": -1}}, "must be positive"),
    ("ok", {"kind": "plt", "units": {"density": 1}}, "density"),
    ("ok", {"kind": "plt", "sources": {}}, "did you mean 'source'"),
    ("ok", {"kind": "plt", "source": {"paht": "plt"}}, "did you mean 'path'"),
])
def test_errors_name_the_key(tmp_path, name, spec, message):
    with pytest.raises(ConfigError, match=message):
        D.load_domain(tag(tmp_path, name, spec))


def test_the_project_files_new_keys(tmp_path):
    (tmp_path / "flowreel.yml").write_text(
        "defaults: {backend: osmesa, style: {font: Lato}}\ntags: [bare]\n")
    project = load_project(tmp_path)
    assert project.defaults == {"backend": "osmesa", "style": {"font": "Lato"}}
    assert project.tag_names == ("bare",) and project.tags == {}
    for text, message in [("defaults: {backend: opengl}\n", "backend"),
                          ("defaults: {colour: red}\n", "colour"),
                          ("tags: bare\n", "list of tag names"),
                          ("tags: [a.b]\n", "no dots")]:
        (tmp_path / "flowreel.yml").write_text(text)
        with pytest.raises(ConfigError, match=message):
            load_project(tmp_path)


def test_the_data_template_command(tmp_path, monkeypatch):
    from cli_harness import Shell
    monkeypatch.chdir(tmp_path)
    status, out, _ = Shell(tmp_path).run("data template --kind vtk")
    assert status == 0 and "kind: vtk" in out and "path: vtk/flow.pvd" in out
    status, out, _ = Shell(tmp_path).run("data template -o data/run/domain.yml")
    assert status == 0 and (tmp_path / "data" / "run" / "domain.yml").is_file()
    status, _, err = Shell(tmp_path).run("data template -o data/run/domain.yml")
    assert status != 0 and "--force" in err
