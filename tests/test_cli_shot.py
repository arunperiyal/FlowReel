"""flowreel shot render, preview, memory and template, on generated data."""
import numpy as np
import pytest
from PIL import Image
from shellkit import CommandError

from flowreel.cli.shot import parse_frames

from cli_harness import Shell

SHOT = """name: g
source: geometry:grooved_cylinder
time: {frozen: 0, frames: 6}
camera: {view: main}
size: [64, 48]
antialias: none
layers:
  - {type: outline, width: 2}
  - {type: geometry, body: grooved_cylinder, colour: "#ff0000"}
"""
CAMERAS = "views:\n  - {name: main, position: [0, -30, 3], focal: [0, 0, 3], up: [0, 0, 1]}\n"


@pytest.fixture
def sh(tmp_path, monkeypatch):
    (tmp_path / "g.yml").write_text(SHOT)
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    monkeypatch.chdir(tmp_path)
    return Shell(tmp_path / "store")


def run(sh, line):
    status, out, err = sh.run(line)
    if status and ("OpenGL" in err or "display" in err.lower()):
        pytest.skip("off-screen rendering is not available")
    return status, out, err


def test_parse_frames():
    assert parse_frames("3") == [3]
    assert parse_frames("0:4") == [0, 1, 2, 3, 4]
    assert parse_frames("0:10:5,7") == [0, 5, 10, 7]
    for bad in ("a", "4:2", "0:4:0", "1:2:3:4", "-1"):
        with pytest.raises(CommandError):
            parse_frames(bad)


def test_render_writes_frames_then_skips_them(sh, tmp_path):
    status, out, err = run(sh, "shot render g.yml -j 2 --frames 0:2")
    assert status == 0, err
    assert "3 rendered, 0 skipped" in out and "frame_00002.png rendered" in out
    assert sorted(p.name for p in (tmp_path / "frames" / "g").glob("*.png")) == \
        ["frame_00000.png", "frame_00001.png", "frame_00002.png"]
    assert "0 rendered, 3 skipped" in run(sh, "shot render g.yml --frames 0:2")[1]
    assert "3 rendered" in run(sh, "shot render g.yml --frames 0:2 --force")[1]


def test_render_a_draft_from_the_shot_context(sh, tmp_path):
    sh.run("use shot:g.yml")
    status, out, err = run(sh, "shot render --frames 1 --size 32 24 -o drafts")
    assert status == 0, err
    img = np.asarray(Image.open(tmp_path / "drafts" / "g@32x24" / "frame_00001.png"))
    assert img.shape == (24, 32, 3)


@pytest.mark.parametrize("line, message", [
    ("shot render g.yml --frames 9", "frame 9 is outside"),
    ("shot render g.yml --scale 0.5 --size 10 10", "not both"),
    ("shot render g.yml -j 0", "at least 1"),
    ("shot render missing.yml", "no such file"),
    ("shot render", "no shot given"),
])
def test_render_errors(sh, line, message):
    status, _, err = sh.run(line)
    assert status != 0 and message in err


def test_shot_file_errors_name_the_key(sh, tmp_path):
    (tmp_path / "bad.yml").write_text(SHOT.replace("size: [64, 48]", "sise: [64, 48]"))
    status, _, err = sh.run("shot render bad.yml")
    assert status == 2 and "bad.yml: sise" in err and "did you mean 'size'" in err


def test_preview_draws_every_nth_and_the_last_small(sh, tmp_path):
    status, out, err = run(sh, "shot preview g.yml --every 4")
    assert status == 0, err
    folder = tmp_path / "frames" / "g@16x12"                    # a quarter of 64 x 48
    assert sorted(p.name for p in folder.glob("*.png")) == ["frame_00000.png", "frame_00004.png",
                                                            "frame_00005.png"]
    assert "3 rendered" in out
    assert run(sh, "shot preview g.yml --every 0")[0] == 2


def test_memory_reports_a_safe_jobs(sh):
    status, out, err = run(sh, "shot memory g.yml --frame 1 --threads 1")
    assert status == 0, err
    assert "frame 1: peak" in out and "suggested jobs: -j" in out
    assert "outside" in sh.run("shot memory g.yml --frame 99")[2]
