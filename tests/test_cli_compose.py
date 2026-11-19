"""flowreel compose layout, on generated data."""
import numpy as np
import pytest
import yaml
from PIL import Image

from cli_harness import Shell
from tests.panel_project import project


@pytest.fixture
def sh(tmp_path, monkeypatch):
    folder = project(tmp_path / "p")
    (folder / "lift.yml").write_text(yaml.safe_dump(
        {"type": "series", "size": [80, 60], "times": [0.0, 1.0, 2.0],
         "lines": [{"body": "bare", "series": "force", "column": "cl"}]}))
    (folder / "flow").mkdir()
    for i in range(3):
        Image.new("RGB", (40, 60), "#ff0000").save(folder / "flow" / f"frame_{i:05d}.png")
    (folder / "board.yml").write_text(yaml.safe_dump({"size": [120, 60], "tiles": [
        {"frames": "flow", "at": [0, 0], "size": [40, 60]},
        {"panel": "lift.yml", "at": [40, 0], "size": [80, 60]}]}))
    monkeypatch.chdir(folder)
    return Shell(tmp_path / "store")


def test_layout_composes_with_its_panel(sh, tmp_path):
    status, out, err = sh.run("compose layout board.yml")
    assert status == 0, err
    assert "3 composed, 0 skipped" in out
    picture = np.asarray(Image.open(tmp_path / "p" / "frames" / "board" / "frame_00000.png"))
    assert picture.shape == (60, 120, 3) and (picture[:, :40] == (255, 0, 0)).all()
    status, out, _ = sh.run("compose layout board.yml")
    assert "0 composed, 3 skipped" in out
    status, out, _ = sh.run("compose layout board.yml --scale 0.5 --frames 0:1")
    assert "2 composed" in out and "board@60x30" in out
    status, out, _ = sh.run("compose layout board.yml --force --frames 2")
    assert "1 composed" in out


def test_errors(sh):
    status, _, err = sh.run("compose layout board.yml --scale 0.5 --size 10 10")
    assert status != 0 and "not both" in err
    status, _, err = sh.run("compose layout nothing.yml")
    assert status != 0 and "nothing.yml" in err
    status, _, err = sh.run("compose layout board.yml -j 0")
    assert status != 0 and "-j" in err
    status, _, err = sh.run("compose")
    assert status != 0


@pytest.mark.parametrize("action", ["layout"])
def test_every_action_has_help_with_examples(action, capsys):
    from flowreel.cli import main
    assert main(["compose", action, "--help"]) == 0
    text = capsys.readouterr().out
    assert f"flowreel compose {action}" in text and "examples:" in text
