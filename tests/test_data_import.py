"""Cases brought into a project as tags (Phase 9, branch 2): data import, list, info,
remove, rename and check, and project init --import."""
import sys
from pathlib import Path

import numpy as np
import pytest
import pyvista as pv
import yaml

from cli_harness import Shell
from flowreel.project import imports as I
from flowreel.project.domain import load_domain

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    case.write_case(tmp_path / "cases" / "a", project=False)
    case.write_case(tmp_path / "cases" / "b", steps=2, project=False)
    monkeypatch.chdir(root)
    return root


def run(line):
    return Shell(Path.cwd()).run(line)


def plt_path(project, which="a"):
    return project.parent / "cases" / which / "case"


def test_a_plt_case_is_linked_and_measured(project):
    status, out, err = run(f"data import plt --path {plt_path(project)} --tag bare")
    assert status == 0, err
    link = project / "data" / "bare" / "plt"
    assert link.is_symlink() and link.resolve() == plt_path(project).resolve()
    domain = load_domain(project / "data" / "bare")
    assert domain.kind == "plt" and domain.bodies["cyl"].axis == "x"
    assert domain.measured["steps"] == {"first": 0, "last": 30, "count": case.STEPS}
    assert domain.measured["zones"] == ["cyl"] and "p" in domain.measured["fields"]
    assert "fill in the units" in out


def test_a_second_import_is_refused_and_force_keeps_the_edits(project):
    assert run(f"data import plt --path {plt_path(project)} --tag bare")[0] == 0
    path = project / "data" / "bare" / "domain.yml"
    path.write_text(path.read_text().replace("units:", "units: {rho: 1000.0, mu: 1.0, u_inf: 1.0}"
                                                       "  # mine\nold_units:", 1)
                    .replace("old_units:", "#"))
    status, _, err = run(f"data import plt --path {plt_path(project, 'b')} --tag bare")
    assert status != 0 and "--force" in err
    status, out, err = run(f"data import plt --path {plt_path(project, 'b')} --tag bare --force")
    assert status == 0 and "updated" in out, err
    domain = load_domain(project / "data" / "bare")
    assert domain.units == {"rho": 1000.0, "mu": 1.0, "u_inf": 1.0}          # kept
    assert domain.measured["steps"]["count"] == 2                             # new case
    assert (project / "data" / "bare" / "plt").resolve() == plt_path(project, "b").resolve()
    assert "# mine" in path.read_text()
    status, _, err = run(f"data import vtk --path {plt_path(project)} --tag bare --force")
    assert status != 0 and "holds a plt case" in err


def test_a_copy_says_its_size_and_keeps_checksums(project, monkeypatch):
    status, out, err = run(f"data import plt --path {plt_path(project)} --tag c --copy")
    assert status == 0, err
    target = project / "data" / "c" / "plt"
    assert target.is_dir() and not target.is_symlink() and "to copy into" in out
    sums = load_domain(project / "data" / "c").measured["checksums"]
    assert len(sums) == case.STEPS and all(len(s) == 64 for s in sums.values())
    monkeypatch.setattr(I, "COPY_LIMIT", 10)
    status, _, err = run(f"data import plt --path {plt_path(project)} --tag d --copy")
    assert status != 0 and "--yes" in err
    status, _, err = run("data remove c")
    assert status != 0 and "copied" in err
    assert run("data remove c --yes")[0] == 0 and not (project / "data" / "c").exists()


def test_a_vtk_case_with_its_body_file(project, tmp_path):
    run_dir = tmp_path / "vtkrun"
    run_dir.mkdir()
    for k in range(2):
        g = pv.ImageData(dimensions=(4, 4, 4)).cast_to_unstructured_grid()
        g.point_data["U"] = np.full(g.n_points, float(k))
        g.point_data["V"] = g.point_data["W"] = np.zeros(g.n_points)
        g.save(run_dir / f"flow_{k}.vtu")
    (run_dir / "flow.pvd").write_text(
        '<VTKFile type="Collection"><Collection>'
        '<DataSet timestep="0" file="flow_0.vtu"/><DataSet timestep="1" file="flow_1.vtu"/>'
        '</Collection></VTKFile>')
    body = tmp_path / "elsewhere" / "wall.vtp"
    body.parent.mkdir()
    pv.Sphere(radius=0.5, center=(1.5, 1.5, 1.5)).save(body)
    status, _, err = run(f"data import vtk --path {run_dir} --tag run --body ball={body}")
    assert status == 0, err
    domain = load_domain(project / "data" / "run")
    assert domain.source["path"].endswith("vtk/flow.pvd")
    assert domain.source["body"] == {"ball": str(project.resolve() / "data" / "run" / "ball.vtp")}
    assert (project / "data" / "run" / "ball.vtp").is_symlink()
    assert "ball" in domain.bodies and domain.measured["steps"]["count"] == 2


def test_a_vtk_flow_may_be_a_pattern(project, tmp_path):
    run_dir = tmp_path / "vtkrun"
    run_dir.mkdir()
    for k in range(2):
        g = pv.ImageData(dimensions=(4, 4, 4)).cast_to_unstructured_grid()
        g.point_data["U"] = g.point_data["V"] = g.point_data["W"] = np.zeros(g.n_points)
        g.save(run_dir / f"flow_{k}.vtu")
    status, _, err = run(f"data import vtk --path {run_dir} --flow 'flow_*.vtu' --tag run")
    assert status == 0, err
    assert load_domain(project / "data" / "run").measured["steps"]["count"] == 2
    status, _, err = run(f"data import vtk --path {run_dir} --flow 'wake_*.vtu' --tag again")
    assert status != 0 and "no wake_*.vtu in" in err


def test_a_geometry_tag(project):
    status, _, err = run("data import geometry --name mass --tag ball --param size=0.5")
    assert status == 0, err
    domain = load_domain(project / "data" / "ball")
    assert domain.kind == "geometry" and domain.source == {"body": "mass", "params": {"size": 0.5}}
    status, out, _ = run("data list")
    assert "ball" in out and "geometry" in out


def test_list_info_and_check(project):
    run(f"data import plt --path {plt_path(project)} --tag bare")
    status, out, _ = run("data list")
    assert status == 0 and "bare" in out and f"{case.STEPS} steps" in out
    status, out, _ = run("data info bare")
    assert "zones:  cyl" in out and "units:  none given" in out
    status, out, _ = run(f"data info {plt_path(project)}")               # any folder
    assert status == 0 and f"steps:  {case.STEPS}" in out
    status, out, _ = run("data check")
    assert status == 1 and "units not given" in out
    path = project / "data" / "bare" / "domain.yml"
    path.write_text(path.read_text().replace("units:", "units: {rho: 1.0, mu: 1.0, u_inf: 1.0}\nx_:", 1)
                    .replace("x_:", "#"))
    status, out, _ = run("data check")
    assert status == 0 and "bare: ok" in out
    (project / "data" / "bare" / "plt").unlink()
    (project / "data" / "bare" / "plt").symlink_to(project / "gone")
    status, out, _ = run("data check")
    assert status == 1 and "does not resolve" in out


def test_remove_leaves_the_case_and_rename_follows_the_files(project):
    run(f"data import plt --path {plt_path(project)} --tag bare")
    (project / "flowreel.yml").write_text("tags: [bare]\n")
    (project / "panels").mkdir()
    (project / "panels" / "lift.yml").write_text(
        "rows:\n  - lines: [{body: bare.cyl, series: force}]\nsource: bare\n")
    status, out, err = run("data rename bare smooth")
    assert status == 0, err
    assert (project / "data" / "smooth" / "domain.yml").is_file()
    assert "smooth.cyl" in (project / "panels" / "lift.yml").read_text()
    assert "source: smooth" in (project / "panels" / "lift.yml").read_text()
    assert yaml.safe_load((project / "flowreel.yml").read_text())["tags"] == ["smooth"]
    status, out, _ = run("data remove smooth")
    assert status == 0 and not (project / "data" / "smooth").exists()
    assert list(plt_path(project).glob("*.plt"))                       # the case is there


def test_project_init_imports_a_case(tmp_path, monkeypatch):
    case.write_case(tmp_path / "cases", project=False)
    monkeypatch.chdir(tmp_path)
    status, out, err = Shell(tmp_path).run(
        f"project init -o film --import plt:{tmp_path / 'cases' / 'case'} --tag bare")
    assert status == 0, err
    assert (tmp_path / "film" / "data" / "bare" / "domain.yml").is_file()
    assert "tag bare" in (tmp_path / "film" / "cameras.yml").read_text()
    assert "data/bare/domain.yml" in out


@pytest.mark.parametrize("line, message", [
    ("data import plt --path {p} --tag a.b", "no dots"),
    ("data import plt --tag x", "--path"),
    ("data import plt --path {p}/nothing --tag x", "not a folder"),
    ("data import geometry --tag g", "--name"),
    ("data import plt --path {p} --tag x --name mass", "geometry tag"),
    ("data remove nobody", "no tag 'nobody'"),
])
def test_errors(project, line, message):
    status, _, err = run(line.format(p=plt_path(project)))
    assert status != 0 and message in err, err


def test_info_of_a_folder_needs_no_project(tmp_path, monkeypatch):
    case.write_case(tmp_path / "cases", project=False)
    monkeypatch.chdir(tmp_path)
    status, out, err = Shell(tmp_path).run(f"data info {tmp_path / 'cases' / 'case'}")
    assert status == 0, err
    assert ": plt" in out and f"steps:  {case.STEPS}" in out and "zones:  cyl" in out
