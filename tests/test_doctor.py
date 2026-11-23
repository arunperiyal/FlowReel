"""flowreel doctor: the report of what FlowReel runs on (flowreel.doctor)."""
import tomllib
from pathlib import Path

from flowreel import doctor as D

ROOT = Path(__file__).parent.parent


def test_the_oldest_tested_versions_are_the_declared_minimums():
    """CI's oldest job installs the minimums of pyproject.toml; TESTED says the same."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    for name, (oldest, newest) in D.TESTED.items():
        line = next(d for d in declared if d.lower().startswith(name + ">="))
        assert line.split(">=")[1] == oldest, (name, line)
        assert D.version_tuple(newest) >= D.version_tuple(oldest)


def test_versions_are_read_as_numbers():
    assert D.version_tuple("9.7.2") == (9, 7, 2)
    assert D.version_tuple("2.1.1rc1") == (2, 1, 1)
    assert D.version_tuple("0.49.dev0") == (0, 49)


def test_each_package_is_judged_against_its_minimum_and_the_tested_range(monkeypatch):
    monkeypatch.setattr(D, "minimums", lambda: {"vtk": "9.3", "pyvista": "0.44", "numpy": "1.26",
                                                "scipy": "1.11.2"})
    have = {"vtk": "9.9.0", "pyvista": "0.40.1", "numpy": "2.4.2", "scipy": None}
    lines = {line.what: line for line in D.package_lines(have.get)}
    assert lines["vtk"].level == "note" and "newer than tested (9.3 to 9.7)" in lines["vtk"].text
    assert lines["pyvista"].level == "problem" and "older than FlowReel needs (0.44)" in lines["pyvista"].text
    assert lines["numpy"].level == "ok" and lines["numpy"].text == "2.4.2 (needs 1.26 or newer)"
    assert lines["scipy"].level == "problem" and lines["scipy"].text.startswith("missing")
    have["vtk"] = "9.7.9"
    assert {l.what: l for l in D.package_lines(have.get)}["vtk"].level == "ok"


def test_the_minimums_are_read_from_the_installed_package():
    found = D.minimums()
    assert found["vtk"] == "9.3" and found["numpy"] == "1.26" and "pytest" not in found


def test_a_problem_fails_the_report_and_a_note_does_not():
    report = D.Report([("packages", [D.Line("vtk", "9.9.0, newer than tested", "note")])])
    assert report.exit_code == 0 and " ? vtk" in report.text()
    assert report.text().endswith("everything FlowReel needs is here")
    report.sections.append(("ffmpeg", [D.Line("ffmpeg", "not found", "problem")]))
    assert report.exit_code == 1 and " ! ffmpeg" in report.text()
    assert report.text().endswith("1 problem (marked !)")


def test_the_project_is_described_when_the_folder_is_in_one(tmp_path):
    assert "not in a project" in D.project_lines(tmp_path)[0].text
    (tmp_path / "flowreel.yml").write_text("")
    (tmp_path / "sub").mkdir()
    lines = {line.what: line.text for line in D.project_lines(tmp_path / "sub")}
    assert lines["folder"] == str(tmp_path.resolve()) and lines["shots"] == "none yet"


def test_the_command(capsys):
    from flowreel.cli import main
    status = main(["doctor", "--no-draw"])
    out = capsys.readouterr().out
    assert "packages:" in out and "vtk" in out and "ffmpeg:" in out and "fonts:" in out
    assert "off-screen drawing" not in out
    assert status == (1 if " ! " in out else 0)
