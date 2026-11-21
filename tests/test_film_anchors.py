"""Captions and shapes anchored in the model: projected per output frame of the film."""
import numpy as np
import pytest
from PIL import Image

from flowreel import film
from flowreel.film.anchors import Anchor, ShotProjector, fitting, place
from flowreel.film.clips import Clips
from flowreel.film.text import parse_caption
from flowreel.scene.errors import Checker
from flowreel.scene.frame_views import DrawnView, save_views
from flowreel.scene.projection import project
from flowreel.scene.views import View

from film_project import decode, film_file, need_ffmpeg

POINT = (0.0, 0.0, 0.0)


def view(i):
    """Frame i's camera: it slides along +x, so the point moves left across the frame."""
    return View((0.3 * i, 0, 10), (0.3 * i, 0, 0), view_angle=40)


def drawn_frames(folder, n, size=(160, 90), record=True):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", size, (110, 110, 110)).save(folder / f"frame_{i:05d}.png")
    if record:
        save_views(folder, {f"frame_{i:05d}.png": DrawnView(view(i), size) for i in range(n)})
    return folder


def expected(i, size=(160, 90), film_size=(160, 90)):
    x, y, _ = project(view(i), POINT, size)[0]
    sx, sy, ox, oy = fitting(size, film_size)
    return x * sx + ox, y * sy + oy


DOT = {"lines": ["x"], "size": 10, "colour": "#00ff00", "shadow": False, "fade": 0,
       "place": [0, 0],
       "shapes": [{"circle": {"centre": {"model": list(POINT)}, "radius": 5, "fill": "#ff0000",
                                       "colour": "#ff0000"}}]}


def load(tmp_path, shots, **top):
    return Clips(film.load(film_file(tmp_path, shots, **top)))


def red_centre(frame):
    f = frame.astype(int)
    ys, xs = np.nonzero((f[..., 0] > 170) & (f[..., 1] < 100) & (f[..., 2] < 100))
    return (xs.mean() + 0.5, ys.mean() + 0.5) if len(xs) else None


def test_projector_follows_the_recorded_camera(tmp_path):
    drawn_frames(tmp_path / "f", 4)
    c = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8}}])
    p = ShotProjector(c.film, c.line, "a")
    a = Anchor(POINT, offset=(3, -2))
    for i in range(4):                                   # output frame 3 i shows frame i
        x, y = p.point(a, 3 * i)
        assert (x - 3, y + 2) == pytest.approx(expected(i))
    half = p.point(Anchor(POINT), 1)                     # a third of the way to frame 1
    lo, hi = expected(0), expected(1)
    assert half == pytest.approx((lo[0] + (hi[0] - lo[0]) / 3, lo[1]))


def test_repeat_keeps_the_point_with_its_frame(tmp_path):
    drawn_frames(tmp_path / "f", 3)
    c = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8, "to_output": "repeat"}}])
    p = ShotProjector(c.film, c.line, "a")
    assert p.point(Anchor(POINT), 1) == pytest.approx(expected(0))


def test_frames_of_another_size_are_fitted(tmp_path):
    drawn_frames(tmp_path / "f", 2, size=(80, 80))
    c = load(tmp_path, [{"name": "a", "frames": "f"}])
    p = ShotProjector(c.film, c.line, "a")
    assert fitting((80, 80), (160, 90)) == (90 / 80, 90 / 80, 35.0, 0.0)
    assert p.point(Anchor(POINT), 1) == pytest.approx(expected(1, (80, 80)))


def test_hidden_behind_or_off_the_frame(tmp_path):
    drawn_frames(tmp_path / "f", 2)
    c = load(tmp_path, [{"name": "a", "frames": "f"}])
    p = ShotProjector(c.film, c.line, "a")
    assert p.point(Anchor((0, 0, 20)), 0) is None           # behind the camera
    assert p.point(Anchor((40, 0, 0)), 0) is None           # far to the side
    cap = parse_caption({**DOT, "place": {"model": [40, 0, 0]},
                         "shapes": [*DOT["shapes"],
                                    {"line": {"from": {"model": [40, 0, 0]}, "to": [1, 1]}}]},
                        Checker())
    placed = place(cap, p, 0)
    assert not placed.text and placed.hidden == 1 and len(placed.caption.shapes) == 1
    assert placed.caption.shapes[0]["centre"] == pytest.approx(expected(0))


def test_view_or_track_for_frames_without_a_record(tmp_path):
    drawn_frames(tmp_path / "f", 3, record=False)
    (tmp_path / "cameras.yml").write_text(
        "views:\n  - {name: v0, position: [0, 0, 10], focal: [0, 0, 0], view_angle: 40}\n"
        "  - {name: v2, position: [0.6, 0, 10], focal: [0.6, 0, 0], view_angle: 40}\n"
        "tracks:\n  t: {ease: linear, keys: [{frame: 0, view: v0}, {frame: 2, view: v2}]}\n")
    c = load(tmp_path, [{"name": "a", "frames": "f"}])
    p = ShotProjector(c.film, c.line, "a")
    assert p.point(Anchor(POINT, view="v0"), 2) == pytest.approx(expected(0))
    assert p.point(Anchor(POINT, track="t"), 1) == pytest.approx(expected(1))
    with pytest.raises(ValueError, match="no recorded camera.*'view' or 'track'"):
        p.point(Anchor(POINT), 0)
    with pytest.raises(ValueError, match="no camera track 'u'"):
        p.point(Anchor(POINT, track="u"), 0)


def test_a_card_has_no_camera(tmp_path):
    (tmp_path / "card.yml").write_text("blocks: [{title: 'T'}]\n")
    c = load(tmp_path, [{"name": "c", "card": "card.yml", "seconds": 1}])
    with pytest.raises(ValueError, match="is a card: it has no camera"):
        ShotProjector(c.film, c.line, "c")


def test_the_finished_clip_draws_the_dot_where_the_point_is(tmp_path):
    need_ffmpeg()
    drawn_frames(tmp_path / "f", 6)
    caption = {**DOT, "at": [0.0, 0.5]}
    c = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8},
                         "text": [caption]}])
    clip = c.finished("a")
    pictures = decode(clip.path)
    assert len(pictures) == 18
    for i in range(6):
        seen = red_centre(pictures[3 * i])
        if 3 * i <= 0.5 * 24:
            assert seen == pytest.approx(expected(i), abs=1.0)
        else:
            assert seen is None                          # after the caption's end
    assert len(list((tmp_path / "clips" / "caption_a_0").glob("frame_*.png"))) == 13   # 0 to 0.5 s
    again = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8},
                             "text": [caption]}]).finished("a")
    assert not again.built                               # same record: kept
    save_views(tmp_path / "f", {"frame_00002.png": DrawnView(view(5), (160, 90))})
    moved = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8},
                             "text": [caption]}]).finished("a")
    assert moved.built                                   # a camera changed: rebuilt


def test_hidden_spans_name_the_caption_and_times(tmp_path):
    from flowreel.film.anchors import hidden_spans
    drawn_frames(tmp_path / "f", 6)
    # The camera slides +0.3 a frame; a point at x = -5.5 leaves the frame on the left
    # partway through, and the arrow to it goes with it.
    gone = [-5.5, 0, 0]
    caption = {**DOT, "lines": ["Look here"], "at": [0.0, 0.75], "place": {"model": gone},
               "shapes": [{"arrow": {"from": [10, 10], "to": {"model": gone}}}]}
    c = load(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8}, "text": [caption]}])
    p = ShotProjector(c.film, c.line, "a")
    shown = [p.point(Anchor(tuple(gone)), j) is not None for j in range(18)]
    first = shown.index(False)
    assert any(shown) and not any(shown[first:])
    spans = hidden_spans(c)
    assert len(spans) == 1
    h = spans[0]
    assert (h.caption, h.shot, h.what) == ("Look here", "a", "text and 1 shape")
    assert h.start == pytest.approx(first / 24) and h.end == pytest.approx(18 / 24)
    assert "'Look here' on shot 'a': text and 1 shape hidden from" in h.message()


def test_film_check_warns(tmp_path, monkeypatch):
    need_ffmpeg()
    from cli_harness import Shell
    drawn_frames(tmp_path / "f", 6)
    caption = {**DOT, "lines": ["Look here"], "at": [0.0, 0.75], "place": {"model": [-5.5, 0, 0]}}
    film_file(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8}, "text": [caption]}])
    monkeypatch.chdir(tmp_path)
    status, out, err = Shell(tmp_path / "store").run("film check --at every:0.5 --width 80")
    assert status == 0, err
    assert "caption 'Look here' on shot 'a': text hidden from" in err


def test_label3d_and_dimension3d_become_2d_shapes(tmp_path):
    from flowreel.film.shapes import parse_shape
    lab = parse_shape({"label3d": {"at": [0, 0, 0], "text": "$D$", "offset": [5, -8]}}, Checker())
    assert lab["at"] == Anchor((0, 0, 0), (5, -8)) and "offset" not in lab.keys
    dim = parse_shape({"dimension3d": {"from": [-1, 0, 0], "to": {"model": [1, 0, 0]},
                                       "value": "$2$", "offset": 12}}, Checker())
    assert dim["from"] == Anchor((-1, 0, 0)) and dim["offset"] == 12
    drawn_frames(tmp_path / "f", 2)
    c = load(tmp_path, [{"name": "a", "frames": "f"}])
    p = ShotProjector(c.film, c.line, "a")
    cap = parse_caption({**DOT, "shapes": [
        {"label3d": {"at": [0, 0, 0], "text": "$D$", "offset": [5, -8]}},
        {"dimension3d": {"from": [-1, 0, 0], "to": [1, 0, 0], "value": "$2$"}}]}, Checker())
    shapes = place(cap, p, 0).caption.shapes
    assert [s.kind for s in shapes] == ["label", "dimension"]
    x, y = expected(0)
    assert shapes[0]["at"] == pytest.approx((x + 5, y - 8))
    left = project(view(0), (-1, 0, 0), (160, 90))[0][:2]
    assert shapes[1]["from"] == pytest.approx(tuple(left))


@pytest.mark.parametrize("spec, message", [
    ({"label3d": {"at": [0, 0], "text": "a"}}, r"label3d\.at"),
    ({"label3d": {"at": [0, 0, 0]}}, "missing key 'text'"),
    ({"dimension3d": {"from": [0, 0, 0], "to": [0, 0, 0]}}, "must differ"),
    ({"label": {"at": [0, 0, 0], "text": "a"}}, r"label\.at"),
])
def test_model_shape_errors(spec, message):
    from flowreel.film.shapes import parse_shape
    from flowreel.scene.errors import ConfigError
    with pytest.raises(ConfigError, match=message):
        parse_shape(spec, Checker())


def test_a_label_is_centred_on_its_point():
    from flowreel.film.draw import caption_image
    from flowreel.film.schema import FilmStyle
    cap = parse_caption({"lines": ["."], "colour": "#00ff00", "shadow": False, "place": [0, 0],
                         "shapes": [{"label": {"at": [120, 40], "text": "O", "size": 30,
                                               "colour": "#ff0000"}}]}, Checker())
    image, _ = caption_image(cap, FilmStyle(), (200, 100))
    centre = red_centre(np.asarray(image.convert("RGB")))
    assert centre == pytest.approx((120, 40), abs=2.5)


def test_draft_frames_put_the_point_where_full_size_ones_do(tmp_path, toy_source):
    from flowreel.scene import render
    from flowreel.scene.camera_path import parse_track
    from flowreel.scene.shot import from_dict
    from flowreel.scene.views import parse_view
    views = {"a": parse_view({"name": "a", "position": [3, 2, 4], "focal": [0, 0, 0.5]}),
             "b": parse_view({"name": "b", "position": [2, -3, 1.5], "focal": [0.2, 0, 0.5]})}
    tracks = {"t": parse_track({"keys": [{"frame": 0, "view": "a"}, {"frame": 2, "view": "b"}]},
                               views)}
    shot = from_dict({"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
                      "camera": {"track": "t"}, "size": [160, 96], "antialias": "none",
                      "layers": [{"type": "body"}]}, file="toy.yml")
    try:
        for scale in (None, 0.5):
            render(shot, source=toy_source, views=views, tracks=tracks, out=tmp_path / "frames",
                   processes=False, scale=scale)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    points = []
    for folder in ("frames/toy", "frames/toy@80x48"):
        c = load(tmp_path, [{"name": "s", "frames": folder, "rate": {"fps": 8}}])
        p = ShotProjector(c.film, c.line, "s")
        points.append([p.point(Anchor((0.1, 0.1, 0.6)), j) for j in range(9)])
    for full, draft in zip(*points):
        assert draft == pytest.approx(full, abs=1e-6)


def test_named_cameras_come_from_the_project_root(tmp_path):
    from flowreel.project import PROJECT_FILE
    films = tmp_path / "films"
    drawn_frames(films / "f", 2, record=False)
    (tmp_path / PROJECT_FILE).write_text("source: toy:none\n")
    (tmp_path / "cameras.yml").write_text(
        "views:\n  - {name: v0, position: [0, 0, 10], focal: [0, 0, 0], view_angle: 40}\n")
    (films / "cameras.yml").write_text(
        "views:\n  - {name: other, position: [0, 0, 5], focal: [0, 0, 0]}\n")
    c = load(films, [{"name": "a", "frames": "f"}])
    p = ShotProjector(c.film, c.line, "a")
    assert p.point(Anchor(POINT, view="v0"), 0) == pytest.approx(expected(0))
    with pytest.raises(ValueError, match="no view 'other'"):
        p.point(Anchor(POINT, view="other"), 0)
