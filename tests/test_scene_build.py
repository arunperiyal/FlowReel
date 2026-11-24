"""A film of scenes built (Phase 10, branch 3): lengths planned and measured, rates and
freezes, fades and cross-fades, a clip per scene kept by its key, subtitles, chapters,
the contact sheet, and the film commands on scenes."""
import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from cli_harness import Shell
from flowreel.film import ffmpeg as ff
from flowreel.film import model as M
from flowreel.film import scene_build as S
from flowreel.film.check import grab
from panel_project import project

FPS = 24
SIZE = [320, 180]


def frames(folder, n, size=(160, 90)):
    """``n`` frames: frame k is grey level 40 k (so frames can be told apart)."""
    folder.mkdir(parents=True)
    for k in range(n):
        Image.new("RGB", size, (40 * k,) * 3).save(folder / f"frame_{k:05d}.png")
    return folder


@pytest.fixture
def root(tmp_path):
    project(tmp_path)
    frames(tmp_path / "frames" / "flow", 6)
    (tmp_path / "panels").mkdir()
    (tmp_path / "panels" / "lift.yml").write_text(
        "type: series\nsize: [320, 240]\ntimes: [0, 0.5, 1, 1.5, 2]\n"
        "rows: [{lines: [{body: bare, series: force, column: cl}]}]\n")
    return tmp_path


def film_file(root, scenes, **more):
    (root / "film.yml").write_text(yaml.safe_dump(
        {"fps": FPS, "size": SIZE, "scenes": scenes, **more}, sort_keys=False))
    return M.load(root / "film.yml")


TITLE = {"name": "title", "seconds": 1.0, "fade": [0.5, 0], "chapter": "Opening",
         "layout": {"boxes": [{"text": {"lines": ["A $C_L$ film"], "size": 30}, "place": "centre",
                               "at": [0.2, None]}]}}
FLOW = {"name": "flow", "cross": 0.5, "chapter": {"title": "The flow", "at": 0.25},
        "layout": {"boxes": [
            {"name": "main", "shot": {"frames": "frames/flow", "rate": {"fps": 12, "to_output": "repeat"},
                                      "freezes": [{"at": 0.25, "hold": 0.5}]}},
            {"text": "Wake", "place": "bottom", "at": [0.1, 0.6]}]}}
END = {"name": "end", "seconds": 1.0, "fade": [0, 0.5], "layout": {"boxes": [{"last_frame": "flow"}]}}


def test_playback_and_the_plan(root):
    p = S.Playback(6, 12, (M.Freeze(0.25, 0.5),))
    assert p.length == pytest.approx(1.0)
    assert [p.position(t) for t in (0, 0.1, 0.25, 0.5, 0.74, 0.75, 0.9, 2)] == \
        pytest.approx([0, 1.2, 3, 3, 3, 3, 4.8, 5])
    film = film_file(root, [TITLE, FLOW, END])
    line = S.plan(film)
    assert [(q.scene.name, q.start, q.length, q.frames) for q in line.scenes] == \
        [("title", 0, 1, 24), ("flow", 1, 1, 24), ("end", 1.5, 1, 24)]
    assert line.length == pytest.approx(2.5)
    assert [(c.title, c.start, c.end) for c in line.chapters] == \
        [("Opening", 0, 1.25), ("The flow", 1.25, 2.5)]
    assert [(s.start, s.end, s.lines) for s in line.subtitles] == \
        [(0.2, 1.0, ("A $C_L$ film",)), (1.1, 1.6, ("Wake",))]
    assert "00:00:00,200 --> 00:00:01,000\nA C_L film" in S.srt_text(line)


def test_a_missing_shot_names_it(root):
    (root / "shots").mkdir()
    (root / "shots" / "nowhere.yml").write_text(
        "{name: nowhere, source: 'x:y', time: {frozen: 0}, layers: [{type: body}]}")
    film = film_file(root, [{"name": "s", "layout": {"boxes": [{"shot": "shots/nowhere.yml"}]}}])
    with pytest.raises(ValueError, match="render it first: flowreel shot render .*nowhere.yml"):
        S.plan(film)


def grey(path, frame):
    return np.asarray(grab(path, frame, tuple(SIZE)))[90, 160].astype(int)


def test_the_film_built_measured_and_kept(root):
    film = film_file(root, [TITLE, FLOW, END])
    built = S.build(film)
    assert [(r.name, r.planned, r.built) for r in built.shots] == \
        [("title", 1, True), ("flow", 1, True), ("end", 1, True)]
    assert built.measured == pytest.approx(2.5, abs=0.05)
    assert ff.length(film.output) == pytest.approx(2.5, abs=0.05)
    assert built.srt.read_text().count("-->") == 2 and built.chapters.is_file()
    assert built.table()[0].startswith("scene")
    clips = {r.name: S.SceneBuilder(film).clip(r.name) for r in built.shots}
    assert ff.frame_count(clips["flow"].path) == 24
    flow = clips["flow"].path
    # repeat at 12 of 24: frame k shows twice; the freeze holds frame 3 (grey 120)
    assert abs(grey(flow, 2) - 40).max() <= 6 and abs(grey(flow, 8) - 120).max() <= 6
    assert abs(grey(flow, 17) - 120).max() <= 6 and abs(grey(flow, 22) - 200).max() <= 6
    assert abs(np.asarray(Image.open(clips["flow"].last))[90, 160].astype(int) - 200).max() <= 1
    # the end holds the flow's last frame, faded out at its end
    end = clips["end"].path
    assert abs(grey(end, 0) - 200).max() <= 6 and grey(end, 23).max() <= 12
    assert grey(clips["title"].path, 0).max() <= 3                    # faded in from black
    # built again: every scene kept
    again = S.build(film)
    assert [r.built for r in again.shots] == [False, False, False]


def test_one_changed_caption_rebuilds_one_scene(root):
    film = film_file(root, [TITLE, FLOW, END])
    S.build(film)
    changed = json.loads(json.dumps(FLOW))
    changed["layout"]["boxes"][1]["text"] = "The wake"
    film = film_file(root, [TITLE, changed, END])
    built = S.build(film)
    assert [(r.name, r.built) for r in built.shots] == \
        [("title", False), ("flow", True), ("end", False)]


def test_interpolated_and_blended_shots_and_a_panel(root):
    box = {"name": "main", "shot": {"frames": "frames/flow", "rate": {"fps": 12, "to_output": "interpolate"}},
           "place": "left"}
    film = film_file(root, [{"name": "s", "layout": {"boxes": [
        box, {"panel": {"file": "panels/lift.yml", "rate": {"fps": 8}}, "place": "right"}]}}])
    assert S.plan(film).scenes[0].frames == 12                    # 6 frames at 12 a second
    clip = S.SceneBuilder(film).clip("s").path
    assert ff.frame_count(clip) == 12
    assert len(list((root / "clips").glob("base_main_*.mkv"))) == 1
    # between frames 2 (80) and 3 (120) at output frame 5: an in-between grey
    mid = np.asarray(grab(clip, 5, tuple(SIZE)))[90, 80].astype(int)
    assert 85 <= mid.mean() <= 115
    blend = dict(box, shot={"frames": "frames/flow", "rate": {"fps": 12, "to_output": "blend"}})
    film = film_file(root, [{"name": "b", "layout": {"boxes": [blend]}}])
    builder = S.SceneBuilder(film)
    timed = builder._timed(film.scenes[0])
    picture = np.asarray(builder.frame("b", 1, timed=timed))
    assert abs(picture[90, 80].astype(int) - 20).max() <= 2       # half of 0 and 40


def test_lengths_and_the_contact_sheet(root):
    film = film_file(root, [TITLE, FLOW, END])
    before = S.lengths(film)
    assert [r.measured for r in before.shots] == [None, None, None]
    S.build(film)
    after = S.lengths(film)
    assert after.measured == pytest.approx(2.5, abs=0.05)
    assert after.table()[0].startswith("scene")
    sheet = S.contact(film)
    assert sheet.is_file() and Image.open(sheet).width > 2 * 240


def test_the_film_commands_on_scenes(root, monkeypatch):
    monkeypatch.chdir(root)
    film_file(root, [TITLE, FLOW, END])
    shell = Shell(root)
    status, out, err = shell.run("film build")
    assert status == 0, err
    assert out.startswith("scene") and "built in" in out
    status, out, _ = shell.run("film lengths")
    assert status == 0 and "film" in out
    status, out, _ = shell.run("film srt")
    assert status == 0 and "2 subtitles" in out
    status, out, _ = shell.run("film chapters")
    assert status == 0 and "0:00 Opening" in out
    status, out, _ = shell.run("film check --at every:1")
    assert status == 0 and "contact.png" in out
    status, out, _ = shell.run("film build --only flow")
    assert status == 0 and (root / "film_flow.mp4").is_file()


def test_a_changed_held_frame_rebuilds_the_scene_holding_it(root):
    film = film_file(root, [TITLE, FLOW, END])
    S.build(film)
    Image.new("RGB", (160, 90), (250, 250, 250)).save(root / "frames" / "flow" / "frame_00005.png")
    built = S.build(M.load(root / "film.yml"))
    assert [(r.name, r.built) for r in built.shots] == \
        [("title", False), ("flow", True), ("end", True)]
