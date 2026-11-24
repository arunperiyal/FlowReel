"""A film of scenes (Phase 10, branch 1): film.yml in levels, layouts of boxes, their
checks, and the templates."""
from pathlib import Path

import pytest
import yaml

from cli_harness import Shell
from flowreel.film import model as M
from flowreel.film.scene_template import film_template, layout_template
from flowreel.scene.errors import ConfigError

SHOT = {"name": "wake", "source": "x", "time": {"frozen": 0}, "layers": [{"type": "body"}]}


@pytest.fixture
def folder(tmp_path):
    for sub in ("shots", "panels", "layouts", "assets"):
        (tmp_path / sub).mkdir()
    (tmp_path / "shots" / "wake.yml").write_text(yaml.safe_dump(SHOT))
    (tmp_path / "panels" / "lift.yml").write_text("type: series\n")
    (tmp_path / "assets" / "logo.png").write_bytes(b"png")
    return tmp_path


def film(folder, scenes, **more):
    return M.from_dict({"scenes": scenes, **more}, file=str(folder / "film.yml"))


def one(folder, *boxes, **scene):
    spec = {"name": "s", "layout": {"boxes": list(boxes)}, **scene}
    return film(folder, [spec]).scenes[0]


def test_the_levels(folder):
    f = film(folder, [
        {"name": "opening", "seconds": 6, "fade": [1.5, 1.5], "chapter": "Opening",
         "layout": {"background": "#101010", "boxes": [
             {"image": "assets/logo.png", "pos": [810, 100], "size": [300, 190]},
             {"name": "title", "text": {"lines": ["Grooves"], "look": "title"}, "place": "centre"}]}},
        {"name": "reveal", "cross": 1.0, "layout": {"boxes": [
            {"shot": {"file": "shots/wake.yml", "rate": {"fps": 12}, "freezes": [{"at": 2, "hold": 3}]}},
            {"text": ["$Re = 1000$"], "place": "bottom", "at": [1, None], "fade": [0.5, 1]}]}},
        {"name": "end", "seconds": 4, "layout": {"boxes": [{"last_frame": "reveal"}]}}],
        style={"looks": {"title": {"size": 70, "weight": "bold"}}})
    opening, reveal, end = f.scenes
    assert opening.layout.background == "#101010" and opening.chapter.title == "Opening"
    image, title = opening.layout.boxes
    assert (image.name, image.kind, image.content.fit) == ("image1", "image", "contain")
    assert title.content.drawn.size == 70.0 and title.rect((1920, 1080)) == (480, 270, 960, 540)  # the film's look
    assert f.style.looks["title"].size == 70 and f.style.looks["title"].weight == "bold"
    shot, caption = reveal.layout.boxes
    assert reveal.layout.main is shot and reveal.seconds is None and reveal.cross == 1.0
    assert shot.content.rate.fps == 12 and shot.content.freezes == (M.Freeze(2.0, 3.0),)
    assert caption.at == (1.0, None) and caption.fade == (0.5, 1.0)
    assert caption.content.lines == ("$Re = 1000$",) and caption.content.subtitle
    assert end.layout.boxes[0].content == M.LastFrame("reveal")


def test_a_layout_in_its_own_file(folder):
    (folder / "layouts" / "compare.yml").write_text(yaml.safe_dump({"boxes": [
        {"name": "main", "shot": "../shots/wake.yml", "place": "left"},
        {"panel": "../panels/lift.yml", "place": "right"}]}))
    scene = film(folder, [{"name": "c", "layout": "compare"}]).scenes[0]
    assert scene.layout.file == folder / "layouts" / "compare.yml"
    assert scene.layout.main.name == "main" and scene.layout.boxes[1].kind == "panel"
    (folder / "layouts" / "bad.yml").write_text(yaml.safe_dump({"boxes": [{"text": {"look": "title"}}]}))
    with pytest.raises(ConfigError, match=r"layouts/bad.yml: boxes\[0\].text: missing key 'lines'"):
        film(folder, [{"name": "c", "layout": "bad", "seconds": 2}])


def test_follow_and_shapes(folder):
    scene = one(folder, {"name": "main", "shot": "shots/wake.yml"},
                {"text": "groove", "follow": {"box": "main", "model": [6, 0.4, 0.2], "offset": [40, -120]}},
                {"shape": {"kind": "arrow", "direction": "down_left"}, "size": [120, 90],
                 "follow": {"box": "main", "model": [6, 0.4, 0.2]}},
                {"shape": {"kind": "rectangle", "fill": "#00000080", "radius": 8},
                 "pos": [40, 40], "size": [500, 200]})
    text, arrow, rect = scene.layout.boxes[1:]
    assert text.follow == M.Follow("main", (6.0, 0.4, 0.2), (40.0, -120.0)) and text.rect((1920, 1080)) is None
    assert arrow.content.kind == "arrow" and arrow.content.direction == "down_left"
    assert rect.content.fill == "#00000080" and rect.rect((1920, 1080)) == (40, 40, 500, 200)


@pytest.mark.parametrize("box, scene, message", [
    ({"text": "a", "image": "assets/logo.png"}, {"seconds": 1}, "give one of .* \\(got text, image\\)"),
    ({}, {"seconds": 1}, "give one of 'text'"),
    ({"txt": "a"}, {"seconds": 1}, "did you mean 'text'"),
    ({"image": "assets/none.png"}, {"seconds": 1}, "no image file"),
    ({"image": "assets/logo.png", "pos": [0, 0]}, {"seconds": 1}, "needs its 'size'"),
    ({"text": "a", "place": "middle"}, {"seconds": 1}, "place"),
    ({"text": "a", "place": "top", "pos": [0, 0]}, {"seconds": 1}, "not two"),
    ({"text": "a", "size": [10, 10]}, {"seconds": 1}, "a size needs 'pos'"),
    ({"text": "a", "at": [3, 2]}, {"seconds": 5}, "end must come after"),
    ({"text": "a", "at": [1, 6]}, {"seconds": 5}, "outside the scene's 5 seconds"),
    ({"text": {"lines": "a", "look": "huge"}}, {"seconds": 1}, "look"),
    ({"shape": {"kind": "line", "fill": "red"}}, {"seconds": 1}, "is for a rectangle or a circle"),
    ({"shape": {"kind": "circle", "head": 10}}, {"seconds": 1}, "is for an arrow"),
    ({"image": "assets/logo.png", "follow": {"box": "x", "model": [0, 0, 0]}}, {"seconds": 1},
     "only text and shape boxes follow"),
    ({"text": "a", "follow": {"box": "x", "model": [0, 0, 0]}}, {"seconds": 1}, "no box 'x'"),
    ({"shot": "shots/wake.yml"}, {"seconds": 3}, "lasts as long as its main box"),
    ({"text": "a"}, {}, "missing key 'seconds'"),
    ({"last_frame": "s"}, {"seconds": 1}, "its own last frame"),
    ({"last_frame": "other"}, {"seconds": 1}, "no scene 'other'"),
    ({"shot": {"file": "shots/wake.yml", "rate": {"fps": 7}}}, {}, "whole number"),
    ({"shot": "shots/none.yml"}, {}, "no shot file"),
    ({"panel": "panels/none.yml"}, {}, "no panel file"),
    ({"text": "a"}, {"seconds": 1, "cross": 1}, "the last scene has no next scene"),
])
def test_errors_name_the_key(folder, box, scene, message):
    with pytest.raises(ConfigError, match=message):
        one(folder, box, **scene)


def test_scene_level_errors(folder):
    text = {"layout": {"boxes": [{"text": "a"}]}, "seconds": 1}
    with pytest.raises(ConfigError, match="scene 'a' is named twice"):
        film(folder, [{"name": "a", **text}, {"name": "a", **text}])
    with pytest.raises(ConfigError, match="a fade out or a cross"):
        film(folder, [{"name": "a", "cross": 1, "fade": [0, 1], **text}, {"name": "b", **text}])
    with pytest.raises(ConfigError, match="box 'n' is named twice"):
        one(folder, {"name": "n", "text": "a"}, {"name": "n", "text": "b"}, seconds=1)
    with pytest.raises(ConfigError, match="no scene 'nope'"):
        film(folder, [{"name": "a", **text}], watermark={"text": "me", "scenes": ["nope"]})
    with pytest.raises(ConfigError, match="no layout file"):
        film(folder, [{"name": "a", "layout": "missing", "seconds": 1}])


def test_the_templates_load(folder):
    (folder / "film.yml").write_text(film_template("wake", 24))
    f = M.load(folder / "film.yml")
    assert [s.name for s in f.scenes] == ["opening", "wake", "end"]
    assert f.scenes[1].layout.main.kind == "shot" and f.scenes[2].seconds == 4
    (folder / "layouts" / "compare.yml").write_text(layout_template())
    layout = M.load_layout(folder / "layouts" / "compare.yml")
    assert [b.kind for b in layout.boxes] == ["shot", "panel", "text", "shape"]
    assert layout.main.name == "main"


def test_the_commands(folder, monkeypatch):
    monkeypatch.chdir(folder)
    status, out, _ = Shell(folder).run("film template wake")
    assert status == 0 and "scenes:" in out and "shots/wake.yml" in out
    status, out, _ = Shell(folder).run("film template --layout")
    assert status == 0 and "boxes:" in out
    (folder / "film.yml").write_text(film_template("wake"))
    (folder / "flowreel.yml").write_text("")
    status, _, err = Shell(folder).run("film check")
    assert status != 0 and "render it first: flowreel shot render" in err   # read, no frames
    from flowreel.project.info import info
    assert info(folder).film == "film.yml: 3 scenes"


def test_a_text_box_starts_from_the_films_look(folder):
    (folder / "layouts" / "l.yml").write_text("boxes: [{text: a}]\n")
    f = film(folder, [{"name": "a", "seconds": 1, "layout": {"boxes": [
        {"text": "a"}, {"text": {"lines": "b", "valign": "top"}}, {"text": {"lines": "c", "look": "title"}}]}},
        {"name": "b", "seconds": 1, "layout": "l"}],
        style={"looks": {"text": {"valign": "bottom", "margin": 80}}})
    a, b, c = f.scenes[0].layout.boxes
    assert (a.content.drawn.valign, a.content.drawn.margin) == ("bottom", 80)
    assert (b.content.drawn.valign, b.content.drawn.margin) == ("top", 80)
    assert c.content.drawn.valign == "centre"                     # the title look's own
    assert f.scenes[1].layout.boxes[0].content.drawn.valign == "bottom"   # a layout file too
