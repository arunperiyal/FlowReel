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
    (folder / "flowreel.yml").write_text("")                # a project (docs/project.md)
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


def test_check(sh, project):
    status, out, err = sh.run("film check --at every:1 --width 80 --columns 2 -o sheet.png")
    assert status == 0, err
    from PIL import Image
    sheet = Image.open(project / "sheet.png")
    assert sheet.width < 2 * 80 + 20 and "sheet.png" in out
    status, _, err = sh.run("film check --at sometimes")
    assert status != 0 and "every:S" in err


def test_lengths_measured_from_the_last_build(sh, project, tmp_path):
    status, out, err = sh.run("film lengths --clips " + str(tmp_path / "none"))
    assert status == 0, err
    rows = words(out)
    assert rows["b"] == ["1.75", "s", "-"] and rows["film"] == [f"{TOTAL:.2f}", "s", "-"]
    assert "no finished clip" in out
    sh.run("film build")
    rows = words(sh.run("film lengths")[1])
    assert rows["b"] == ["1.75", "s", "1.75", "s"]
    assert rows["Middle"] == ["0:01", "1.25", "s", "2.00", "s"]
    assert rows["End"] == ["0:03", "3.25", "s", "1.00", "s"]


def test_srt_and_chapters(sh, project):
    status, out, err = sh.run("film srt -o subs.srt")
    assert status == 0, err
    assert "2 captions" in out and (project / "subs.srt").read_text().startswith("1\n00:00:00,250")
    status, out, err = sh.run("film chapters")
    assert status == 0
    assert out == "0:00 Start\n0:01 Middle\n0:03 End\n" and "YouTube's 10 s" in err
    status, out, _ = sh.run("film chapters -o ch.txt")
    assert (project / "ch.txt").read_text() == "0:00 Start\n0:01 Middle\n0:03 End\n"


def test_template(sh, tmp_path):
    status, out, _ = sh.run("film template")
    assert status == 0 and "name: my_shot" in out and out.startswith("# Film file")
    target = tmp_path / "t.yml"
    assert sh.run(f"film template wake --fps 30 -o {target}")[0] == 0
    assert "fps: 30" in target.read_text()
    status, _, err = sh.run(f"film template -o {target}")
    assert status != 0 and "--force" in err
    assert sh.run(f"film template -o {target} --force")[0] == 0


def test_project_context_finds_film_yml(project, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    sh = Shell(tmp_path / "store")
    status, _, err = sh.run("film lengths")
    assert status != 0 and "film.yml" in err
    assert sh.run(f"use project:{project}")[0] == 0
    status, out, err = sh.run("film lengths")
    assert status == 0, err
    assert words(out)["b"][:2] == ["1.75", "s"] and str(project / "film.yml") in out + err
    status, _, err = sh.run(f"use project:{elsewhere}")
    assert status != 0 and "not a project" in err
