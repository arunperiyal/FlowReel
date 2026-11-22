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


# -- generated output under the root ------------------------------------------------------

SHOT = """name: g
source: geometry:grooved_cylinder
time: {frozen: 0, frames: 3}
camera: {view: main}
size: [64, 48]
antialias: none
layers:
  - {type: geometry, body: grooved_cylinder, colour: "#ff0000"}
"""
CAMERAS = "views:\n  - {name: main, position: [0, -30, 3], focal: [0, 0, 3], up: [0, 0, 1]}\n"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "flowreel.yml").write_text("")
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    (tmp_path / "shots").mkdir()
    (tmp_path / "g.yml").write_text(SHOT)
    return tmp_path


def test_output_goes_under_the_root_wherever_a_command_runs(project, monkeypatch):
    monkeypatch.chdir(project / "shots")
    sh = Shell(project / "store")
    status, out, err = sh.run("shot render ../g.yml --frames 0:2 -j 2")
    if status and ("OpenGL" in err or "display" in err.lower()):
        pytest.skip("off-screen rendering is not available")
    assert status == 0, err
    assert len(list((project / "frames" / "g").glob("frame_*.png"))) == 3
    assert not (project / "shots" / "frames").exists()
    assert (project / ".flowreel" / "measured" / "frames" / "g.json").is_file()
    assert not (project / "frames" / "g" / ".measured.json").exists()
    status, _, err = sh.run("shot render ../g.yml --frames 0 -o elsewhere")    # -o still overrides
    assert status == 0, err
    assert (project / "shots" / "elsewhere" / "g" / "frame_00000.png").is_file()


def test_caches_and_records_are_machine_state(project, tmp_path_factory):
    from flowreel.jobs import measured
    from flowreel.project.paths import output
    from flowreel.scene.rendering import surface_cache
    from flowreel.scene.shot import load
    shot = load(project / "g.yml")
    assert surface_cache(shot, "anything") == project / ".flowreel" / "cache" / "surfaces"
    assert measured.path(project / "frames" / "g@32x24") == \
        project / ".flowreel" / "measured" / "frames" / "g@32x24.json"
    assert output(project / "shots" / "film.yml", "clips") == project / "clips"
    away = tmp_path_factory.mktemp("away")                       # the library, outside one
    assert measured.path(away / "g") == away / "g" / ".measured.json"
    assert output(away / "film.yml", "clips") == away / "clips"
    rec = measured.Measured(10, 1.0, 1, 1, "h", "now")
    (project / "frames" / "old").mkdir(parents=True)
    (project / "frames" / "old" / ".measured.json").write_text(
        '{"peak_bytes": 10, "seconds": 1.0, "threads": 1, "frames": 1, "host": "h", "when": "now"}')
    assert measured.load(project / "frames" / "old") == rec       # an older record is read


def test_jobs_run_at_the_root(project, monkeypatch):
    from flowreel.jobs.run import _workdir
    monkeypatch.chdir(project / "shots")
    assert _workdir(None) == project


# -- one cameras.yml at the root -----------------------------------------------------------

def test_one_cameras_file_at_the_root_serves_shots_below_it(project):
    from flowreel.project.paths import cameras_file
    from flowreel.scene.camera import shot_camera
    from flowreel.scene.shot import load
    (project / "shots" / "g.yml").write_text(SHOT)
    assert cameras_file(project / "shots" / "g.yml") == project / "cameras.yml"
    shot_camera(load(project / "shots" / "g.yml"))                  # found at the root
    (project / "shots" / "cameras.yml").write_text(CAMERAS)          # left beside the shot
    with pytest.raises(Exception, match="one cameras.yml, at its root; move this one to"):
        shot_camera(load(project / "shots" / "g.yml"))


def test_camera_commands_write_the_root_file(project, monkeypatch):
    (project / "shots" / "g.yml").write_text(SHOT)
    monkeypatch.chdir(project / "shots")
    sh = Shell(project / "store")
    status, out, err = sh.run("camera path intro --keys 0:main 12:main")
    assert status == 0, err
    assert "intro" in (project / "cameras.yml").read_text()
    assert not (project / "shots" / "cameras.yml").exists()
    (project / "shots" / "cameras.yml").write_text(CAMERAS)
    status, _, err = sh.run("camera preview intro g.yml --every 12")
    assert status != 0 and "move this one to" in err


# -- project info and project clean --------------------------------------------------------

def test_project_info_lists_what_the_project_holds(tmp_path, monkeypatch):
    from flowreel import sources
    make_project(tmp_path, sources.create("geometry", body="grooved_cylinder"))
    (tmp_path / "shots" / "g.yml").write_text(SHOT)
    (tmp_path / "shots" / "broken.yml").write_text("source: x\nlayers: [\n")   # not YAML: skipped
    (tmp_path / "frames" / "g").mkdir(parents=True)
    for i in range(2):
        (tmp_path / "frames" / "g" / f"frame_{i:05d}.png").write_bytes(b"x" * 500)
    (tmp_path / ".flowreel" / "cache").mkdir(parents=True)
    (tmp_path / ".flowreel" / "cache" / "s.vtp").write_bytes(b"x" * 2000)
    monkeypatch.chdir(tmp_path / "shots")
    status, out, err = Shell(tmp_path / "store").run("project info")
    assert status == 0, err
    assert f"project {tmp_path}" in out
    assert "source:  geometry:grooved_cylinder" in out and "bodies:  grooved_cylinder" in out
    assert "shots/g.yml: g, 2 frames drawn" in out and "broken" not in out
    assert "cameras: views main; tracks none" in out
    assert "film:    film.yml: 1 shot" in out          # the template's shot; its frames are missing
    assert "frames/ 1.0 kB" in out and ".flowreel/ 2.0 kB" in out


def test_project_clean(tmp_path, monkeypatch):
    make_project(tmp_path)
    for rel, n in (("frames/g/frame_00000.png", 1000), (".flowreel/cache/surfaces/a.vtp", 3000),
                   (".flowreel/measured/frames/g.json", 10), ("clips/g.mp4", 500)):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"x" * n)
    monkeypatch.chdir(tmp_path)
    sh = Shell(tmp_path / "store")
    status, out, err = sh.run("project clean --frames --dry-run")
    assert status == 0, err
    assert "would remove frames/ (1.0 kB)" in out and (tmp_path / "frames" / "g").is_dir()
    status, out, err = sh.run("project clean")                     # the caches by default
    assert status == 0 and "removed .flowreel/cache/ (3.0 kB)" in out, err
    assert not (tmp_path / ".flowreel" / "cache").exists()
    assert (tmp_path / ".flowreel" / "measured" / "frames" / "g.json").is_file()   # kept
    status, out, err = sh.run("project clean --frames --clips")
    assert status == 0 and "removed 1.5 kB in all" in out, err
    assert not (tmp_path / "frames").exists() and not (tmp_path / "clips").exists()
    assert (tmp_path / "film.yml").is_file() and (tmp_path / "cameras.yml").is_file()
    assert "nothing to remove" in sh.run("project clean --cache")[1]
    scratch = tmp_path.parent / f"{tmp_path.name}_scratch"
    scratch.mkdir()
    (tmp_path / "frames").symlink_to(scratch)
    status, _, err = sh.run("project clean --frames")
    assert status == 0 and "skipped frames: a link" in err and scratch.is_dir()


def test_info_and_clean_stop_outside_a_project(sh):
    for line in ("project info", "project clean --dry-run"):
        status, _, err = sh.run(line)
        assert status != 0 and "not in a FlowReel project" in err
