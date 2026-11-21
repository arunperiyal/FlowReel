import numpy as np
import pytest

from flowreel.scene.camera_path import load_tracks, parse_track
from flowreel.scene.errors import ConfigError
from flowreel.scene.views import View, load_views


def v(x, angle=30.0, **kw):
    return View((x, 0, 10), (x, 0, 0), view_angle=angle, **kw)


VIEWS = {"a": v(0), "b": v(10, 50), "c": v(30), "p": v(0, parallel=True, parallel_scale=5)}


def track(**kw):
    spec = {"keys": [{"frame": 0, "view": "a"}, {"frame": 10, "view": "b"}], "ease": "linear"}
    spec.update(kw)
    return parse_track(spec, VIEWS)


def test_linear_blend_and_clamping():
    t = track()
    assert t.at(-5) == VIEWS["a"] and t.at(99) == VIEWS["b"]
    mid = t.at(5)
    assert mid.position == (5, 0, 10) and mid.focal == (5, 0, 0) and mid.view_angle == 40


def test_default_ease_is_smooth():
    t = parse_track({"keys": [{"frame": 0, "view": "a"}, {"frame": 10, "view": "b"}]}, VIEWS)
    assert t.at(2.5).position[0] == pytest.approx(10 * (0.25 ** 2 * (3 - 0.5)))


def test_spline_passes_through_keys_and_bends():
    keys = [{"frame": 0, "view": "a"}, {"frame": 10, "view": "b"}, {"frame": 20, "view": "c"}]
    t = parse_track({"keys": keys, "path": "spline", "ease": "linear"}, VIEWS)
    assert t.at(10).position == pytest.approx((10, 0, 10))
    lin = parse_track({"keys": keys, "ease": "linear"}, VIEWS)
    assert t.at(5).position[0] != lin.at(5).position[0]       # uneven spacing: curve differs
    assert np.isfinite(t.at(15).position).all()


def test_projection_switch_does_not_blend():
    t = parse_track({"keys": [{"frame": 0, "view": "a"}, {"frame": 4, "view": "p"}],
                     "ease": "linear"}, VIEWS)
    assert not t.at(3).parallel and t.at(4).parallel


@pytest.mark.parametrize("spec, msg", [
    ({"keys": [{"frame": 0, "view": "z"}]}, r"keys\[0\].view: 'z' is not allowed"),
    ({"keys": [{"frame": 5, "view": "a"}, {"frame": 5, "view": "b"}]}, r"keys\[1\].frame: frames must increase"),
    ({"keys": [{"frame": 0, "view": "a"}], "path": "splin"}, "did you mean 'spline'"),
    ({"keys": []}, "at least 1"),
    ({"keys": [{"frame": 0}]}, "missing key 'view'"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_track(spec, VIEWS)


def test_load_tracks(tmp_path):
    p = tmp_path / "cameras.yml"
    p.write_text("views:\n  - {name: a, position: [0,0,5], focal: [0,0,0]}\n"
                 "  - {name: b, position: [5,0,0], focal: [0,0,0]}\n"
                 "tracks:\n  t: {frames: 9, path: spline, keys: [{frame: 0, view: a}, {frame: 8, view: b}]}\n")
    t = load_tracks(p, load_views(p))["t"]
    assert t.frames == 9 and t.path == "spline"


def test_key_ease_sets_its_segment():
    keys = [{"frame": 0, "view": "a"}, {"frame": 10, "view": "b", "ease": "hold"},
            {"frame": 20, "view": "c"}]
    t = parse_track({"keys": keys, "ease": "linear"}, VIEWS)
    assert t.eases == (None, "hold", None)
    assert t.at(5).position[0] == pytest.approx(5)            # track's linear
    assert t.at(15).position == VIEWS["b"].position            # held until the next key
    assert t.at(20).position == VIEWS["c"].position


def test_key_ease_errors_name_the_key():
    keys = [{"frame": 0, "view": "a", "ease": "fast"}, {"frame": 10, "view": "b"}]
    with pytest.raises(ConfigError, match=r"keys\[0\]\.ease"):
        parse_track({"keys": keys}, VIEWS)
    keys = [{"frame": 0, "view": "a"}, {"frame": 0, "view": "b"}]
    with pytest.raises(ConfigError, match=r"keys\[1\]\.frame.*must increase"):
        parse_track({"keys": keys}, VIEWS)


def test_build_track():
    from flowreel.scene.camera_path import build_track
    t = build_track(VIEWS, [(0, "a"), (10, "b", "in"), (20, "c")], path="spline")
    assert t.path == "spline" and t.eases == (None, "in", None)
    assert t.at(10).position == pytest.approx(VIEWS["b"].position)
    assert build_track(VIEWS, [(0, "a"), (5, "b")]).eases == ()
    for keys, msg in [([], "at least one"), ([(0, "a"), (0, "b")], "must increase"),
                      ([(0, "zz")], "no view named 'zz'"), ([(0, "a", "bad")], "unknown ease")]:
        with pytest.raises(ValueError, match=msg):
            build_track(VIEWS, keys)
    with pytest.raises(ValueError, match="unknown path"):
        build_track(VIEWS, [(0, "a")], path="bezier")
