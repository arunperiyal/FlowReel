"""shot render records each frame's camera (.views.json), and it projects onto the picture."""
import numpy as np
import pytest
from PIL import Image

from flowreel.scene import render
from flowreel.scene.camera_path import parse_track
from flowreel.scene.frame_views import VIEWS_FILE, DrawnView, load_views, save_views
from flowreel.scene.shot import from_dict
from flowreel.scene.views import View, parse_view

VIEWS = {"near": parse_view({"name": "near", "position": [3, 2, 4], "focal": [0, 0, 0.5]}),
         "side": parse_view({"name": "side", "position": [2, -3, 1.5], "focal": [0.2, 0, 0.5]})}
TRACKS = {"move": parse_track({"keys": [{"frame": 0, "view": "near"},
                                        {"frame": 2, "view": "side"}]}, VIEWS)}


def shot(**extra):
    spec = {"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": {"track": "move"}, "size": [96, 64], "antialias": "none",
            "layers": [{"type": "body", "colour": "#ff0000"}]}
    spec.update(extra)
    return from_dict(spec, file="toy.yml")


def run(tmp_path, toy_source, **kw):
    try:
        return render(shot(), source=toy_source, views=VIEWS, tracks=TRACKS, out=tmp_path,
                      processes=False, **kw)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")


def test_render_records_each_frames_view(tmp_path, toy_source):
    report = run(tmp_path, toy_source)
    record = load_views(report.folder)
    assert sorted(record) == ["frame_00000.png", "frame_00001.png", "frame_00002.png"]
    for i in range(3):
        drawn = record[f"frame_{i:05d}.png"]
        expect = TRACKS["move"].at(i)
        assert drawn.size == (96, 64) and drawn.stretch is None
        assert drawn.view.position == pytest.approx(expect.position)
        assert drawn.view.focal == pytest.approx(expect.focal)


def test_the_record_projects_onto_the_drawn_body(tmp_path, toy_source):
    report = run(tmp_path, toy_source)
    for i in range(3):
        name = f"frame_{i:05d}.png"
        img = np.asarray(Image.open(report.folder / name))
        red = (img[:, :, 0] > 100) & (img[:, :, 1] < 60)
        ys, xs = np.nonzero(red)
        x, y, depth = load_views(report.folder)[name].pixels((0, 0, 0.5))[0]
        assert depth > 0
        assert x == pytest.approx(xs.mean() + 0.5, abs=1.0)        # the sphere's centre
        assert y == pytest.approx(ys.mean() + 0.5, abs=1.0)


def test_skipped_frames_and_drafts_are_recorded(tmp_path, toy_source):
    run(tmp_path, toy_source, frames=[0])
    (tmp_path / "toy" / VIEWS_FILE).unlink()
    report = run(tmp_path, toy_source, frames=[0, 1])
    assert report.count("skipped") == 1
    assert sorted(load_views(report.folder)) == ["frame_00000.png", "frame_00001.png"]
    draft = run(tmp_path, toy_source, scale=0.5)
    assert draft.folder.name == "toy@48x32"
    assert {d.size for d in load_views(draft.folder).values()} == {(48, 32)}


def test_stretch_is_recorded_and_applied(tmp_path):
    view = View((0, 0, 10), (0, 0, 0), view_angle=60)
    plain = DrawnView(view, (100, 100))
    squeezed = DrawnView(view, (100, 100), (0.5, 1, 1))
    assert squeezed.pixels((2, 0, 0))[0][:2] == pytest.approx(plain.pixels((1, 0, 0))[0][:2])
    save_views(tmp_path, {"frame_00000.png": squeezed})
    save_views(tmp_path, {"frame_00001.png": plain})
    back = load_views(tmp_path)
    assert back["frame_00000.png"] == squeezed and back["frame_00001.png"] == plain


def test_no_record():
    assert load_views("/nonexistent/folder") == {}
