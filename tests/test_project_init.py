"""flowreel project init: a flowreel.yml with a measured body per surface zone."""
import pytest
import pyvista as pv

from flowreel.project import PROJECT_FILE, load_project
from flowreel.project.init import bodies_yaml, init_project

from cli_harness import Shell
from conftest import ToySource
from test_project_measure import tube


class Zones(ToySource):
    """Two zones: a riser 40 D long along x and a ball that is not slender."""

    name = "zones"

    def bodies(self):
        return ["cyl", "ball"]

    def body(self, step, name=None):
        return tube(bend=0.5) if name == "cyl" else pv.Sphere(radius=0.3, center=(5, 3, 0))


def test_every_zone_becomes_a_measured_body(tmp_path):
    path = init_project(tmp_path, Zones(), label="vtk:run.pvd")
    text = path.read_text()
    assert text.startswith("# flowreel.yml written by `flowreel project init` from vtk:run.pvd at step 0.")
    bodies = load_project(path).bodies
    assert list(bodies) == ["cyl", "ball"]
    cyl, ball = bodies["cyl"], bodies["ball"]
    assert cyl.zone == "cyl" and cyl.axis == "x" and cyl.diameter == pytest.approx(1.0, rel=1e-3)
    assert cyl.ends == ()                                  # supports are left to fill
    assert ball.axis is None and ball.diameter is None     # a diameter is for beams
    assert "# axis: x" in text and "not slender" in text


def test_the_commented_supports_are_valid_once_uncommented(tmp_path):
    text = bodies_yaml(Zones())
    filled = "\n".join(line.replace("    # ends:", "    ends:").replace("    #   - {at", "      - {at")
                       for line in text.splitlines())
    (tmp_path / PROJECT_FILE).write_text(filled)
    ends = load_project(tmp_path).bodies["cyl"].ends
    assert [(e.at, e.support) for e in ends] == [(0.0, "clamped"), (40.0, "clamped")]


def test_init_refuses_to_overwrite(tmp_path):
    init_project(tmp_path, Zones())
    with pytest.raises(FileExistsError, match="use --force"):
        init_project(tmp_path, Zones())
    init_project(tmp_path, Zones(), force=True)


def test_a_source_without_bodies():
    class Bare(ToySource):
        def bodies(self):
            return []
    with pytest.raises(LookupError, match="no surface zone"):
        bodies_yaml(Bare())


def test_project_init_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sh = Shell(tmp_path / "store")
    status, out, err = sh.run("project init geometry:grooved_cylinder -o carve")
    assert status == 0, err
    assert "wrote carve/flowreel.yml: 1 body (grooved_cylinder)" in out
    body = load_project(tmp_path / "carve").bodies["grooved_cylinder"]
    assert body.axis is not None and body.diameter == pytest.approx(1.0, rel=0.01)   # grooves do not count
    status, _, err = sh.run("project init geometry:grooved_cylinder -o carve")
    assert status != 0 and "use --force" in err
    status, _, err = sh.run("project init grooved_cylinder")
    assert status != 0 and "adapter:location" in err
    status, _, err = sh.run("project init geometry:grooved_cylinder --step 7 -o other")
    assert status != 0 and "step 7 is not saved" in err


def test_project_init_help(capsys):
    from flowreel.cli import main
    assert main(["project", "init", "--help"]) == 0
    assert "flowreel project init plt:bare/BR0SG0U1P0" in capsys.readouterr().out


def test_body_option_names_bodies():
    from shellkit import CommandError
    from flowreel.cli.project import body_option
    assert body_option(None) is None
    assert body_option(["wall.vtp"]) == "wall.vtp"
    assert body_option(["cylinder=wall.vtp"]) == {"cylinder": "wall.vtp"}
    assert body_option(["a=a.vtp", "b=b_*.vtp"]) == {"a": "a.vtp", "b": "b_*.vtp"}
    for bad, words in ((["a.vtp", "b.vtp"], "a name each"), (["a.vtp", "b=b.vtp"], "or one FILE"),
                       (["=b.vtp"], "NAME=FILE"), (["a=x", "a=y"], "given twice")):
        with pytest.raises(CommandError, match=words):
            body_option(bad)


def test_project_init_names_a_vtk_body(tmp_path, monkeypatch):
    flow = pv.ImageData(dimensions=(5, 5, 5), spacing=(1, 1, 1)).cast_to_unstructured_grid()
    flow.point_data["U"] = flow.points[:, 0]
    flow.save(tmp_path / "flow.vtu")
    tube(length=4.0, rings=9).save(tmp_path / "wall.vtp")
    monkeypatch.chdir(tmp_path)
    status, out, err = Shell(tmp_path / "store").run(
        "project init vtk:flow.vtu --body cylinder=wall.vtp")
    assert status == 0, err
    assert "1 body (cylinder)" in out
    assert load_project(tmp_path).bodies["cylinder"].zone == "cylinder"
