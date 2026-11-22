"""The project rules (plan Section 23, question 6): the folder project init makes, the
data link, and commands that find the project by walking up and stop outside one."""
import pytest

from flowreel.project import load_project
from flowreel.project.init import gitignore_text, make_project
from flowreel.project.paths import FOLDERS, IGNORED, NotInProject, find_root, require_root
from flowreel.scene.views import load_views

from cli_harness import Shell


@pytest.fixture
def sh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return Shell(tmp_path / "store")


def test_init_makes_the_agreed_folders_and_files(tmp_path):
    from flowreel import sources
    made = make_project(tmp_path / "p", sources.create("geometry", body="grooved_cylinder"))
    root = tmp_path / "p"
    assert all((root / name).is_dir() for name in FOLDERS)
    assert {p.name for p in made.wrote if p.is_file()} == \
        {"flowreel.yml", "film.yml", "cameras.yml", ".gitignore"}
    assert list(load_project(root).bodies) == ["grooved_cylinder"]
    view = load_views(root / "cameras.yml")["main"]
    assert view.focal[2] == 0 and view.position[2] > 0          # the domain, seen from +z
    assert "frames: frames/p" in (root / "film.yml").read_text()
    lines = (root / ".gitignore").read_text().splitlines()
    assert all(line in lines for line in IGNORED)


def test_init_keeps_what_a_person_wrote(tmp_path):
    (tmp_path / "film.yml").write_text("# mine\n")
    (tmp_path / ".gitignore").write_text("*.pyc\nframes\n")
    make_project(tmp_path)
    assert (tmp_path / "film.yml").read_text() == "# mine\n"
    text = (tmp_path / ".gitignore").read_text()
    assert text.startswith("*.pyc\nframes\n") and text.count("frames") == 1
    assert "clips/" in text and gitignore_text(text) == text      # a second run adds nothing
    assert load_project(tmp_path).bodies == {}                    # no source: comments only
    with pytest.raises(FileExistsError, match="use --force"):
        make_project(tmp_path)
    make_project(tmp_path, force=True)
    assert (tmp_path / "film.yml").read_text() == "# mine\n"      # even with --force


def test_init_links_the_data_and_never_copies_it(sh, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "big.dat").write_text("x")
    status, out, err = sh.run(f"project init -o p --link {run}")
    assert status == 0, err
    link = tmp_path / "p" / "data" / "run"
    assert link.is_symlink() and link.resolve() == run and "linked" in out
    assert sh.run(f"project init -o p --link {run} --force")[0] == 0   # same link: kept
    other = tmp_path / "other" / "run"
    other.mkdir(parents=True)
    status, _, err = sh.run(f"project init -o q --link {run}")
    assert status == 0, err
    (tmp_path / "q" / "flowreel.yml").unlink()
    status, _, err = sh.run(f"project init -o q --link {other}")
    assert status != 0 and "not" in err and "use --force to" in err
    status, _, err = sh.run("project init -o r --link missing")
    assert status != 0 and "no such file" in err


def test_init_reads_the_source_through_the_link(sh, tmp_path):
    import shutil
    from pathlib import Path
    geo = tmp_path / "case"
    geo.mkdir()
    examples = Path(__file__).parent.parent / "examples" / "shot_commands"
    shutil.copy(examples / "shot.yml", geo / "shot.yml")
    status, out, err = sh.run(f"project init -o p --link {geo} geometry:grooved_cylinder")
    assert status == 0, err
    assert "1 body (grooved_cylinder)" in out and "made p:" in out


def test_commands_find_the_project_by_walking_up(tmp_path, monkeypatch):
    (tmp_path / "flowreel.yml").write_text("")
    deep = tmp_path / "shots" / "a"
    deep.mkdir(parents=True)
    assert find_root(deep) == tmp_path
    assert find_root(deep / "s.yml") == tmp_path
    monkeypatch.chdir(deep)
    assert require_root() == tmp_path


def test_commands_stop_outside_a_project(sh, tmp_path):
    with pytest.raises(NotInProject, match="flowreel project init"):
        require_root(tmp_path)
    (tmp_path / "s.yml").write_text("name: s\n")
    for line in ("shot render s.yml", "shot preview s.yml", "camera project --view main "
                 "--points 0,0,0", "compose layout s.yml", "film lengths"):
        status, _, err = sh.run(line)
        assert status != 0 and "not in a FlowReel project" in err, line
        assert "flowreel project init" in err
    for line in ("shot template", "film template", "jobs partitions"):   # these work anywhere
        assert sh.run(line)[0] == 0, line
    status, _, err = sh.run(f"use project:{tmp_path}")
    assert status != 0 and "flowreel project init" in err
