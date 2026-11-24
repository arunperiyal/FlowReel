"""One frame of a scene (Phase 10, branch 2): boxes drawn against pictures drawn by hand,
and text and arrow boxes against the old captions' golden pictures."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.film import boxes as B
from flowreel.film import model as M
from flowreel.scene.frame_views import DrawnView
from flowreel.scene.views import View
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

DATA = Path(__file__).parent / "data" / "captions"
GREY = (90, 110, 130, 255)
PAD = 20


def seen(image):
    """``image`` (RGBA) over mid-grey, as an RGB array."""
    return np.asarray(Image.alpha_composite(Image.new("RGBA", image.size, GREY), image).convert("RGB"))


def compare(picture, gold_image):
    """The difference inside the golden caption's extent, padded."""
    ys, xs = np.nonzero(np.asarray(gold_image)[..., 3])
    top, bottom = max(0, ys.min() - PAD), ys.max() + PAD
    left, right = max(0, xs.min() - PAD), xs.max() + PAD
    gold = seen(gold_image)
    return difference(picture[top:bottom, left:right], gold[top:bottom, left:right])

SIZE = (1920, 1080)


def film_of(tmp_path, boxes, **scene):
    spec = {"name": "s", "layout": {"boxes": boxes}, **({"seconds": 4} if not scene else scene)}
    return M.from_dict({"scenes": [spec]}, file=str(tmp_path / "film.yml"))


def layer(film, contents=None):
    """The scene's boxes over transparency, for the golden comparisons."""
    scene = film.scenes[0]
    out = Image.new("RGBA", film.size, (0, 0, 0, 0))
    for box in scene.layout.boxes:
        out = Image.alpha_composite(out, B.box_image(box, film, scene.layout, contents or B.Contents()))
    return out


def test_a_text_box_and_an_arrow_match_the_boxed_caption(tmp_path):
    film = film_of(tmp_path, [
        {"text": {"lines": ["Each groove $0.08D$ deep and $0.2D$ wide,", "rms $C_L$ falls by $60\\%$"],
                  "size": 40, "align": "left", "box": True}, "pos": [700, 120]},
        {"shape": {"kind": "arrow", "direction": "down_right"}, "pos": [1250, 230], "size": [171, 191]}])
    gold = Image.open(DATA / "boxed.png").convert("RGBA")
    mean, clear = compare(seen(layer(film)), gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


def test_a_bottom_text_and_shadowed_arrows_match_the_shadow_caption(tmp_path):
    arrow = {"kind": "arrow", "width": 6, "head": 27, "shadow": True, "colour": "#f5a142"}
    film = film_of(tmp_path, [
        {"text": {"lines": ["Lift along the span, $C_L(x/D, tU/D)$",
                            "the cells of the smooth cylinder break up"],
                  "colour": "#f5a142", "valign": "bottom", "margin": 80}, "place": "bottom"},
        {"shape": {**arrow, "direction": "up_left"}, "pos": [480, 640], "size": [161, 211]},
        {"shape": {**arrow, "direction": "up_right"}, "pos": [1280, 640], "size": [161, 211]}])
    gold = Image.open(DATA / "shadow.png").convert("RGBA")
    mean, clear = compare(seen(layer(film)), gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


def test_a_text_box_moved_fails_the_same_limits(tmp_path):
    film = film_of(tmp_path, [
        {"text": {"lines": ["Each groove $0.08D$ deep and $0.2D$ wide,", "rms $C_L$ falls by $60\\%$"],
                  "size": 40, "align": "left", "box": True}, "pos": [704, 123]},
        {"shape": {"kind": "arrow", "direction": "down_right"}, "pos": [1250, 230], "size": [171, 191]}])
    gold = Image.open(DATA / "boxed.png").convert("RGBA")
    mean, clear = compare(seen(layer(film)), gold)
    assert mean >= MEAN_LIMIT or clear >= CLEAR_LIMIT


@pytest.fixture
def picture(tmp_path):
    """A 100 x 50 picture: red, with a blue right half."""
    a = np.zeros((50, 100, 3), np.uint8)
    a[:, :50] = (255, 0, 0)
    a[:, 50:] = (0, 0, 255)
    path = tmp_path / "assets" / "p.png"
    path.parent.mkdir()
    Image.fromarray(a).save(path)
    return path


def frame(film, t=1.0, contents=None, length=None):
    return np.asarray(B.draw_frame(film, film.scenes[0], t, contents, length))


@pytest.mark.parametrize("fit, red, blue, black", [
    # 100 x 50 into 300 x 300 at (100, 100): three times, 300 x 150, centred (y 175 to 325)
    ("contain", [(150, 180), (150, 320)], [(350, 180)], [(150, 170), (150, 330)]),
    # six times, 600 x 300, its middle 300 x 300 kept: red to x = 250, then blue
    ("cover", [(110, 105), (220, 395)], [(280, 105), (390, 395)], [(95, 250)]),
    ("stretch", [(105, 105), (220, 395)], [(280, 105), (395, 395)], [(405, 250)]),
])
def test_an_image_fits_its_box(tmp_path, picture, fit, red, blue, black):
    film = film_of(tmp_path, [{"image": {"file": "assets/p.png", "fit": fit},
                               "pos": [100, 100], "size": [300, 300]}])
    a = frame(film)
    for points, colour in ((red, [255, 0, 0]), (blue, [0, 0, 255]), (black, [0, 0, 0])):
        for x, y in points:
            assert a[y, x].tolist() == colour, (fit, x, y, a[y, x])


def test_opacity_and_fades(tmp_path, picture):
    film = film_of(tmp_path, [{"image": {"file": "assets/p.png", "fit": "stretch", "opacity": 0.5},
                               "pos": [0, 0], "size": [100, 100], "at": [1, 3], "fade": [1, 0.5]}])
    box = film.scenes[0].layout.boxes[0]
    assert [B.opacity(box, t, 4) for t in (0.5, 1, 1.5, 2, 2.75, 3, 3.5)] == \
        [0, 0, 0.5, 1, 0.5, 0, 0]
    assert frame(film, 1.5)[50, 10, 0] == round(255 * 0.5 * 0.5)
    text = film_of(tmp_path, [{"text": "a", "at": [1, None]}]).scenes[0].layout.boxes[0]
    assert B.opacity(text, 1.4, 4) == pytest.approx(0.5)            # the text look's 0.8 s
    whole = film_of(tmp_path, [{"text": "a"}]).scenes[0].layout.boxes[0]
    assert B.opacity(whole, 0.0, 4) == 1.0                           # no 'at': no fade


def test_shapes_in_their_boxes(tmp_path):
    film = film_of(tmp_path, [
        {"shape": {"kind": "rectangle", "colour": "#ff0000", "width": 2}, "pos": [10, 10], "size": [100, 50]},
        {"shape": {"kind": "rectangle", "fill": "#00ff0080"}, "pos": [200, 10], "size": [100, 50]},
        {"shape": {"kind": "line", "colour": "#ffffff", "width": 3}, "pos": [10, 200], "size": [300, 3]},
        {"shape": {"kind": "circle", "colour": "#0000ff", "width": 2}, "pos": [400, 10], "size": [100, 100]}])
    a = frame(film)
    assert a[10, 50].tolist() == [255, 0, 0] and a[35, 60].tolist() == [0, 0, 0]
    assert a[35, 250].tolist() == [0, 128, 0]                         # half see-through green
    assert a[201, 15].tolist() == [255, 255, 255] and a[201, 300].tolist() == [255, 255, 255]
    assert a[205, 150].tolist() == [0, 0, 0]
    assert a[11, 450].tolist() == [0, 0, 255] and a[60, 450].tolist() == [0, 0, 0]


def test_a_text_box_sits_by_its_look_in_its_box(tmp_path):
    rect = (100, 100, 600, 300)
    look = M.Look(size=40, shadow=False, align="left", valign="top", margin=20)
    _, block = B.text_image(["Hello"], look, M.Style(), SIZE, rect=rect)
    assert block[0] == 120 and block[1] == 120
    look = M.Look(size=40, shadow=False, align="right", valign="bottom", margin=20)
    _, block = B.text_image(["Hello"], look, M.Style(), SIZE, rect=rect)
    assert block[2] == pytest.approx(680) and block[3] == pytest.approx(380)


def test_shot_and_held_pictures_are_fitted(tmp_path, picture):
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "w.yml").write_text(
        "{name: w, source: x, time: {frozen: 0}, layers: [{type: body}]}")
    film = M.from_dict({"scenes": [
            {"name": "a", "layout": {"boxes": [{"name": "main", "shot": "shots/w.yml", "place": "left"}]}},
            {"name": "b", "seconds": 2, "layout": {"boxes": [{"last_frame": "a", "place": "right"}]}}]},
        file=str(tmp_path / "film.yml"))
    a = np.asarray(B.draw_frame(film, film.scenes[0], 0, B.Contents({"main": picture}), length=3))
    assert a[540, 100].tolist() == [255, 0, 0] and a[540, 900].tolist() == [0, 0, 255]
    assert a[200, 480].tolist() == [0, 0, 0]                          # 960 x 480 centred
    assert a[305, 240].tolist() == [255, 0, 0]                        # its top, 300 down
    b = np.asarray(B.draw_frame(film, film.scenes[1], 0, B.Contents({"last_frame1": picture})))
    assert a[540, 100].tolist() == b[540, 1060].tolist()
    nothing = np.asarray(B.draw_frame(film, film.scenes[0], 0, None, length=3))
    assert nothing.max() == 0                                         # no picture: nothing


def test_a_box_follows_a_point_of_the_flow(tmp_path):
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "w.yml").write_text(
        "{name: w, source: x, time: {frozen: 0}, layers: [{type: body}]}")
    film = M.from_dict({"scenes": [{"name": "a", "layout": {"boxes": [
        {"name": "main", "shot": "shots/w.yml", "place": "left"},
        {"name": "label", "text": "here", "follow": {"box": "main", "model": [0, 0, 0], "offset": [10, -20]}},
        {"name": "tip", "shape": {"kind": "arrow", "direction": "down_right"}, "size": [50, 40],
         "follow": {"box": "main", "model": [0, 0, 0]}}]}}]}, file=str(tmp_path / "film.yml"))
    layout = film.scenes[0].layout
    view = DrawnView(View((0, 0, 10), (0, 0, 0)), (200, 100))
    contents = B.Contents({}, {"main": view})
    # the centre of a 200 x 100 picture, fitted into the left half (960 x 1080): 4.8 times,
    # 300 pixels down to centre it
    assert B.follow_point(layout.box("label"), layout, contents, SIZE) == pytest.approx((490, 520))
    assert B.anchored_rect(layout.box("tip"), (480, 540)) == pytest.approx((431, 501, 50, 40))
    behind = B.Contents({}, {"main": DrawnView(View((0, 0, -10), (0, 0, -20)), (200, 100))})
    assert B.box_image(layout.box("label"), film, layout, behind) is None
    assert B.box_image(layout.box("label"), film, layout, B.Contents()) is None


def test_a_panel_box_is_drawn_at_the_box_size(tmp_path):
    from panel_project import project
    project(tmp_path)
    (tmp_path / "lift.yml").write_text(
        "type: series\nsize: [320, 240]\ntimes: [0, 1]\nrows: [{lines: [{body: bare, series: force, column: cl}]}]\n")
    drawer = B.PanelDrawer(tmp_path / "lift.yml", (640, 360))
    first, later = drawer.at(0.5), drawer.at(1.5)
    assert first.size == (640, 360) and later.size == (640, 360)
    assert np.asarray(first).tolist() != np.asarray(later).tolist()


def test_the_points_boxes_follow_for_the_camera_editor(tmp_path):
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "w.yml").write_text(
        "{name: wake, source: x, time: {frozen: 0}, layers: [{type: body}]}")
    film = M.from_dict({"scenes": [{"name": "a", "layout": {"boxes": [
        {"name": "main", "shot": "shots/w.yml"},
        {"text": ["Groove", "0.08 D"], "follow": {"box": "main", "model": [6, 0.4, 0.2]}},
        {"name": "tip", "shape": "arrow", "size": [40, 40], "follow": {"box": "main", "model": [1, 2, 3]}}]}}]},
        file=str(tmp_path / "film.yml"))
    assert B.follow_points(film, "wake") == [("Groove", (6.0, 0.4, 0.2)), ("tip", (1.0, 2.0, 3.0))]
    assert B.follow_points(film, "other") == []
