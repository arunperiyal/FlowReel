"""Phase 10, branch 4: the panel and scene commands, shots drawn at their box's size, and
project info and the doctor on scenes and layouts."""
from pathlib import Path

import pytest
import yaml
from PIL import Image

from cli_harness import Shell
from flowreel.compose.panel_template import TYPES, template
from flowreel.scene.shot import load as load_shot
from panel_project import project

SHOT = {"name": "wake", "source": "x", "time": {"frozen": 0}, "layers": [{"type": "body"}]}


@pytest.fixture
def root(tmp_path, monkeypatch):
    project(tmp_path)
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "wake.yml").write_text(yaml.safe_dump(SHOT))
    (tmp_path / "shots" / "sized.yml").write_text(yaml.safe_dump({**SHOT, "name": "sized", "size": [640, 360]}))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def film(root, scenes, size=(1920, 1080)):
    (root / "film.yml").write_text(yaml.safe_dump({"fps": 24, "size": list(size), "scenes": scenes}))


def test_a_shot_is_drawn_at_the_size_of_its_box(root):
    assert load_shot(root / "shots" / "wake.yml").size == (1920, 1080)        # no film yet
    film(root, [
        {"name": "a", "layout": {"boxes": [{"shot": "shots/wake.yml", "place": "left"},
                                           {"shot": "shots/sized.yml", "place": "right"}]}},
        {"name": "b", "layout": {"boxes": [{"shot": "shots/wake.yml", "pos": [0, 0], "size": [1400, 900]}]}}])
    assert load_shot(root / "shots" / "wake.yml").size == (1400, 900)         # the larger box
    assert load_shot(root / "shots" / "sized.yml").size == (640, 360)         # its own size
    film(root, [{"name": "a", "layout": {"boxes": [{"shot": "shots/wake.yml", "place": "top_left"}]}}])
    assert load_shot(root / "shots" / "wake.yml").size == (960, 540)          # the film changed


@pytest.mark.parametrize("kind", TYPES)
def test_a_panel_template_of_each_type(kind):
    data = yaml.safe_load(template(kind))
    assert data["type"] == kind and "size" in data and "times" in data


def test_panel_draw_and_template(root):
    (root / "lift.yml").write_text(
        "type: series\nsize: [320, 240]\ntimes: [0, 1]\nrows: [{lines: [{body: bare, series: force, column: cl}]}]\n")
    status, out, err = Shell(root).run("panel draw lift.yml")
    assert status == 0, err
    assert "2 drawn, 0 skipped" in out and (root / "frames" / "lift" / "frame_00001.png").is_file()
    status, out, _ = Shell(root).run("panel draw lift.yml")
    assert "0 drawn, 2 skipped" in out
    status, out, _ = Shell(root).run("panel template --type map -o panels/map.yml")
    assert status == 0 and yaml.safe_load((root / "panels" / "map.yml").read_text())["type"] == "map"
    status, _, err = Shell(root).run("panel template -o panels/map.yml")
    assert status != 0 and "--force" in err


def frames(folder, n):
    folder.mkdir(parents=True)
    for k in range(n):
        Image.new("RGB", (160, 90), (40 * k,) * 3).save(folder / f"frame_{k:05d}.png")


SCENES = [
    {"name": "title", "seconds": 2, "chapter": "Opening", "cross": 0.5,
     "layout": {"boxes": [{"text": "A film", "place": "centre"}]}},
    {"name": "flow", "layout": {"boxes": [{"name": "main", "shot": {"frames": "frames/flow", "rate": {"fps": 12}}},
                                          {"text": "Wake", "place": "bottom", "at": [0.1, 0.4]}]}},
    {"name": "end", "seconds": 1, "layout": "end"},
]


def test_scene_list(root):
    (root / "layouts").mkdir()
    (root / "layouts" / "end.yml").write_text(yaml.safe_dump({"boxes": [{"last_frame": "flow"}]}))
    film(root, SCENES, (320, 180))
    status, out, err = Shell(root).run("scene list")
    assert status != 0 or "?" in out                      # no frames yet: length unknown
    assert "has no frames" in err
    frames(root / "frames" / "flow", 6)
    status, out, err = Shell(root).run("scene list")
    assert status == 0, err
    lines = out.splitlines()
    assert lines[1].split()[:5] == ["title", "0.00", "s", "2.00", "s"]
    assert lines[2].split()[:5] == ["flow", "1.50", "s", "0.50", "s"]
    assert "main (shot, main)" in lines[2] and "chapter 'Opening'" in lines[1]
    assert "layout end.yml" in lines[3] and lines[4].split()[:3] == ["film", "3.00", "s"]


def test_scene_preview(root):
    (root / "layouts").mkdir()
    (root / "layouts" / "end.yml").write_text(yaml.safe_dump({"boxes": [{"last_frame": "flow"}]}))
    frames(root / "frames" / "flow", 6)
    film(root, SCENES, (320, 180))
    status, out, err = Shell(root).run("scene preview flow --at 0 0.25")
    assert status == 0, err
    stills = root / "frames" / "scenes" / "flow"
    assert sorted(p.name for p in stills.iterdir()) == ["at_0.00.png", "at_0.25.png"]
    picture = Image.open(stills / "at_0.25.png")
    assert picture.size == (320, 180) and picture.getpixel((160, 20))[0] == 120   # frame 3
    status, out, err = Shell(root).run("scene preview end")
    assert status == 0 and "not built yet" in err
    status, _, err = Shell(root).run("scene preview flow --at 9")
    assert status != 0 and "outside scene 'flow'" in err
    status, _, err = Shell(root).run("scene preview nope")
    assert status != 0 and "no scene 'nope'" in err


def test_project_info_and_the_doctor_on_scenes(root):
    (root / "layouts").mkdir()
    (root / "layouts" / "end.yml").write_text(yaml.safe_dump({"boxes": [{"last_frame": "flow"}]}))
    film(root, SCENES, (320, 180))
    from flowreel.doctor import project_lines
    from flowreel.project.info import info
    text = info(root).text()
    assert "film:    film.yml: 3 scenes" in text and "scenes:  title, flow, end" in text
    assert "layouts: end" in text
    assert {(line.what, line.text) for line in project_lines(root)} >= {("layouts", "end")}
