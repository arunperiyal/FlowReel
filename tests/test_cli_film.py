"""flowreel film commands, on the tiny generated film of test_film_tiny."""
import pytest

from cli_harness import Shell
from film_project import need_ffmpeg
from test_film_tiny import TOTAL, make


def words(out: str) -> dict[str, list[str]]:
    """Each printed line's words after its first, by its first."""
    return {w[0]: w[1:] for w in (line.split() for line in out.splitlines()) if w}


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    need_ffmpeg()
    folder = tmp_path_factory.mktemp("cli_film")
    make(folder)
    return folder


@pytest.fixture
def sh(project, tmp_path, monkeypatch):
    monkeypatch.chdir(project)
    return Shell(tmp_path / "store")


def test_build_then_keep(sh, project):
    status, out, err = sh.run("film build --preview 46")
    assert status == 0, err
    rows = words(out)
    assert rows["a"] == ["1.25", "s", "1.25", "s", "built"]
    assert rows["film"][0] == f"{TOTAL:.2f}" and rows["preview"][0].endswith("film_46p.mp4")
    assert (project / "film.mp4").is_file() and (project / "film_46p.mp4").is_file()
    status, out, _ = sh.run("film build film.yml --mute")
    assert status == 0 and "built" not in out.replace("built in", "") and "audio: muted" in out


def test_build_only(sh, project):
    status, out, err = sh.run("film build --only b")
    assert status == 0, err
    assert words(out)["b"][:3] == ["1.75", "s", "1.75"] and (project / "film_b.mp4").is_file()


def test_build_errors(sh):
    status, _, err = sh.run("film build --crf 20")
    assert status != 0 and "--preview" in err
    status, _, err = sh.run("film build --preview 45")
    assert status != 0 and "even" in err
    status, _, err = sh.run("film build --only nobody")
    assert status != 0 and "no shot 'nobody'" in err
    status, _, err = sh.run("film build --only a --preview 46")
    assert status != 0 and "whole film" in err
    status, _, err = sh.run("film build missing.yml")
    assert status != 0 and "missing.yml" in err
    status, _, err = sh.run("film build -j 0")
    assert status != 0 and "-j" in err
    status, _, _ = sh.run("film")
    assert status != 0
