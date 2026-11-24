"""flowreel project init: the folders and first files of a project, and a case as a tag."""
import sys
from pathlib import Path

import pytest

from flowreel.project import PROJECT_FILE, load_project
from flowreel.project.init import init_project
from flowreel.project.paths import FOLDERS

from cli_harness import Shell

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402


def test_init_writes_a_project_that_loads(tmp_path):
    path = init_project(tmp_path)
    assert path.name == PROJECT_FILE and path.read_text().startswith("# flowreel.yml")
    assert load_project(path).tag_names == ()


def test_init_refuses_to_overwrite(tmp_path):
    init_project(tmp_path)
    with pytest.raises(FileExistsError, match="use --force"):
        init_project(tmp_path)
    init_project(tmp_path, force=True)


def test_project_init_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sh = Shell(tmp_path / "store")
    status, out, err = sh.run("project init -o carve")
    assert status == 0, err
    assert "made carve: shots/ panels/ layouts/ assets/ data/" in out
    assert FOLDERS == ("shots", "panels", "layouts", "assets", "data")
    assert all((tmp_path / "carve" / name).is_dir() for name in FOLDERS)
    assert not (tmp_path / "carve" / "text").exists() and not (tmp_path / "carve" / "cards").exists()
    status, _, err = sh.run("project init -o carve")
    assert status != 0 and "use --force" in err
    status, _, err = sh.run("project init geometry:grooved_cylinder -o other")
    assert status != 0                      # the forms before tags are gone: no SOURCE
    status, _, err = sh.run("project init --link /tmp -o other")
    assert status != 0


def test_project_init_help(capsys):
    from flowreel.cli import main
    assert main(["project", "init", "--help"]) == 0
    text = capsys.readouterr().out
    assert "flowreel project init --import plt:/scratch/run/binary --tag bare" in text
    assert "SOURCE" not in text and "--link" not in text


def test_project_init_imports_a_case_as_a_tag(tmp_path, monkeypatch):
    case.write_case(tmp_path / "cases")
    monkeypatch.chdir(tmp_path)
    status, out, err = Shell(tmp_path / "store").run(
        f"project init -o film --import plt:{tmp_path / 'cases' / 'case'} --tag bare")
    assert status == 0, err
    assert (tmp_path / "film" / "data" / "bare" / "domain.yml").is_file()
    assert "data/bare/domain.yml" in out
