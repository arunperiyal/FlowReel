"""Shots and panels that name a tag (Phase 9, branch 5): ``source: bare``, ``{tag: bare,
...}``, bodies as ``tag.body`` where tags meet, and frame keys, project info, the doctor
and the camera editor following."""
import sys
from pathlib import Path

import pytest
import yaml

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict as panel_from_dict
from flowreel.scene.errors import ConfigError
from flowreel.scene.rendering import Scene, open_source, source_id
from flowreel.scene.shot import from_dict as shot_from_dict

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

VIEWS = {"main": {"position": [2, 0, 12], "focal": [2, 0, 0], "up": [0, 1, 0]}}


def tag(root, name, units, series=True):
    """A tag of the generated cylinder case, its body cyl with a force series."""
    cases = root.parent / "cases" / name
    case.write_case(cases)
    folder = root / "data" / name
    (folder / "series").mkdir(parents=True)
    (folder / "plt").symlink_to(cases / "case", target_is_directory=True)
    body = {"zone": "cyl", "axis": "x", "diameter": 1.0}
    if series:
        (folder / "series" / "force.csv").write_text(
            "time,fy\n0,0\n1," + str(units["rho"]) + "\n2,0\n")
        body["series"] = {"force": {"file": "series/force.csv"}}
    (folder / "domain.yml").write_text(yaml.safe_dump(
        {"kind": "plt", "source": {"path": "plt"}, "units": units, "bodies": {"cyl": body}}))
    return folder


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "film"
    (root / "shots").mkdir(parents=True)
    (root / "flowreel.yml").write_text("tags: [bare, helical]\n")
    tag(root, "bare", {"rho": 2.0, "u_inf": 1.0, "mu": 0.5})
    tag(root, "helical", {"rho": 1000.0, "u_inf": 1.0, "mu": 1.0})
    return root


def shot(root, source, **more):
    spec = {"name": "s", "source": source, "time": {"frozen": 0, "frames": 1},
            "camera": {"view": "main"}, "size": [32, 18],
            "layers": [{"type": "slice", "normal": "x", "position": 2.0,
                        "field": "pressure_coefficient", "range": [-1, 1]}], **more}
    return shot_from_dict(spec, file=str(root / "shots" / "s.yml"))


def test_a_shot_names_its_tag(project):
    s = shot(project, "bare")
    assert s.source == ("tag", "bare")
    scene = Scene.make(s, views=VIEWS)
    assert scene.source.tag == "bare" and "cyl" in scene.source.declared
    assert scene.reference == {"rho": 2.0, "u_inf": 1.0, "mu": 0.5}
    data = scene.data(0)
    data.need("pressure_coefficient")                           # q = 1/2 rho u_inf^2 = 1
    assert data.flow.point_data["pressure_coefficient"] == pytest.approx(data.flow.point_data["p"])


def test_a_shot_gives_reading_options_with_its_tag(project):
    s = shot(project, {"tag": "helical", "kind": "plt", "margin": 1.5})
    assert open_source(s).tag == "helical"
    key = source_id(s)
    assert key[0] == "tag" and key[1]["source"]["margin"] == 1.5
    assert key[1]["units"]["rho"] == 1000.0


def test_the_frame_key_changes_with_the_tags_units(project):
    before = source_id(shot(project, "bare"))
    path = project / "data" / "bare" / "domain.yml"
    data = yaml.safe_load(path.read_text())
    data["units"]["rho"] = 3.0
    path.write_text(yaml.safe_dump(data))
    assert source_id(shot(project, "bare")) != before


@pytest.mark.parametrize("source, message", [
    ("nobody", "no tag 'nobody'.*tags: bare, helical"),
    ({"tag": "bare", "kind": "vtk"}, "holds a plt case, not vtk"),
    ({"tag": "bare", "names": {}}, "not an option of a plt tag: names"),
    ({"tag": "bare", "adapter": "plt"}, "not an option of a plt tag: adapter"),
    ({"tag": "a.b"}, "letters, digits"),
])
def test_errors_name_the_shot_and_key(project, source, message):
    with pytest.raises(ConfigError, match=message):
        open_source(shot(project, source))


def test_a_tag_needs_a_project(tmp_path):
    s = shot_from_dict({"name": "s", "source": "bare", "time": {"frozen": 0},
                        "layers": [{"type": "body"}]}, file=str(tmp_path / "s.yml"))
    with pytest.raises(ConfigError, match="no project"):
        open_source(s)


def series_panel(root, lines):
    return panel_from_dict({"type": "series", "size": [320, 240], "times": [0, 1],
                            "rows": [{"lines": lines}]}, file=str(root / "lift.yml"))


def test_where_tags_meet_a_body_is_tag_body(project):
    kind = panels.make(series_panel(project, [{"body": "bare.cyl", "series": "force"},
                                              {"body": "helical.cyl", "series": "force"}]))
    names = [line.body for _, lines in kind.rows for line, _ in lines]
    assert names == ["bare.cyl", "helical.cyl"]
    files = kind.files()
    assert files[0].parent.parent.name == "bare" and files[1].parent.parent.name == "helical"
    with pytest.raises(ConfigError, match="bare.cyl or helical.cyl"):
        panels.make(series_panel(project, [{"body": "cyl", "series": "force"}]))
    with pytest.raises(ConfigError, match="declared for bare.cyl, helical.cyl"):
        panels.make(series_panel(project, [{"series": "force"}]))


def test_a_body_of_the_only_tag_is_named_alone(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    tag(root, "bare", {"rho": 2.0, "u_inf": 1.0, "mu": 0.5})
    kind = panels.make(series_panel(root, [{"series": "force"}]))
    assert [line.body for _, lines in kind.rows for line, _ in lines] == ["bare.cyl"]
    kind = panels.make(series_panel(root, [{"body": "cyl", "series": "force"}]))
    assert kind.rows[0][1][0][0].body == "cyl"


def test_a_flow_panel_reads_a_tag_with_its_units(project):
    kind = panels.make(panel_from_dict(
        {"type": "section", "size": [240, 135], "times": [0], "source": "helical",
         "body": "cyl", "station": 2.0, "field": "pressure_coefficient", "range": [-1, 1]},
        file=str(project / "section.yml")))
    assert kind.source.tag == "helical" and kind.params == {"rho": 1000.0, "u_inf": 1.0}
    assert kind.source_id[1]["tag"] == "helical"


def test_project_info_the_doctor_and_the_camera_editor(project):
    from flowreel.cli.camera import _shot_source
    from flowreel.doctor import project_lines
    from flowreel.project.info import info
    (project / "shots" / "s.yml").write_text(yaml.safe_dump(
        {"name": "s", "source": "bare", "time": {"frozen": 0}, "layers": [{"type": "body"}]}))
    found = info(project)
    assert [n for n, _, _ in found.tags] == ["bare", "helical"]
    assert "tags:    bare (plt); helical (plt)" in found.text() and "bare.cyl" in found.text()
    assert "source:  bare" in found.text()
    assert _shot_source(project / "shots" / "s.yml").tag == "bare"
    (project / "data" / "helical" / "plt").unlink()
    (project / "data" / "helical" / "plt").symlink_to(project / "gone")
    lines = {(l.what, l.level): l.text for l in project_lines(project)}
    assert lines[("tags", "ok")] == "bare, helical"
    assert "link does not resolve" in lines[("tag helical", "note")]
