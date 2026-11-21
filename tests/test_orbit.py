import math

import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.orbit import STEP, body_target, orbit
from flowreel.tracks import EASINGS

TARGET = (6.0, 0.0, 9.5)


def test_keys_on_the_circle_looking_at_the_target():
    views, track = orbit(TARGET, radius=12, frames=241, azimuth=-30, span=120, ease="linear")
    assert len(views) == math.ceil(120 / STEP) + 1 and list(views)[0] == "orbit_00"
    for v in views.values():
        assert v.focal == pytest.approx(TARGET)
        assert np.linalg.norm(np.subtract(v.position, TARGET)) == pytest.approx(12)
        assert v.position[1] == pytest.approx(0)                     # elevation 0, axis y
    first, last = views["orbit_00"], list(views.values())[-1]
    assert np.subtract(first.position, TARGET) == pytest.approx(
        12 * np.array([math.cos(math.radians(-30)), 0, -math.sin(math.radians(-30))]))
    assert np.subtract(last.position, TARGET) == pytest.approx(
        12 * np.array([math.cos(math.radians(90)), 0, -math.sin(math.radians(90))]), abs=1e-6)
    assert track.frames == 241 and track.path == "spline"
    assert [k[0] for k in track.keys] == pytest.approx(np.linspace(0, 240, len(views)))
    mid = track.at(115)                                    # between keys: still near the circle
    assert np.linalg.norm(np.subtract(mid.position, TARGET)) == pytest.approx(12, rel=1e-3)


def test_positive_span_turns_anticlockwise_seen_from_the_axis_tip():
    views, _ = orbit((0, 0, 0), radius=1, frames=10, span=90, axis="z", ease="linear")
    vs = list(views.values())
    assert vs[0].position == pytest.approx((1, 0, 0))
    assert vs[-1].position == pytest.approx((0, 1, 0), abs=1e-9)
    assert vs[0].up == (0, 0, 1)


def test_elevation_blends_and_lead_moves_focal():
    views, _ = orbit((0, 0, 0), radius=2, frames=50, span=30, elevation=(10, 40), lead=1.5,
                     axis="x", up=(0, 1, 0))
    vs = list(views.values())
    for v, el in zip((vs[0], vs[-1]), (10, 40)):
        assert v.focal == pytest.approx((1.5, 0, 0))
        assert v.position[0] == pytest.approx(2 * math.sin(math.radians(el)))
    assert vs[0].position[2] == pytest.approx(2 * math.cos(math.radians(10)))   # azimuth 0: +z


def test_ease_spaces_key_frames():
    views, track = orbit(TARGET, radius=5, frames=101, span=90, ease="smooth")
    frames = [k[0] for k in track.keys]
    assert frames[0] == 0 and frames[-1] == 100
    for i, f in enumerate(frames):                         # ease(frame / 100) = i / n
        assert EASINGS["smooth"](f / 100) == pytest.approx(i / (len(frames) - 1), abs=1e-6)
    gaps = np.diff(frames)
    assert gaps[0] > gaps[len(gaps) // 2]                  # slow start


@pytest.mark.parametrize("kw, msg", [
    ({"radius": 0}, "radius"), ({"frames": 1}, "frames"), ({"span": 0}, "span"),
    ({"elevation": 90}, "elevation"), ({"axis": "w"}, "axis"), ({"axis": (0, 0, 0)}, "axis"),
    ({"ease": "hold"}, "ease"), ({"up": (1, 0, 0)}, "parallel"),
])
def test_bad_arguments(kw, msg):
    args = {"target": (0, 0, 0), "radius": 1.0, "frames": 20, **kw}
    with pytest.raises(ValueError, match=msg):
        orbit(**args)


def test_written_and_read_back(tmp_path):
    from flowreel.scene.camera_file import update_cameras
    from flowreel.scene.camera_path import load_tracks
    from flowreel.scene.views import load_views
    views, track = orbit(TARGET, radius=12, frames=120, span=60, elevation=(5, 20), name="turn")
    path = update_cameras(tmp_path / "cameras.yml", views, {"turn": track})
    back = load_views(path)
    assert back == views and load_tracks(path, back)["turn"] == track


class Rod:
    name = "rod"

    def steps(self):
        return [100, 200]

    def bodies(self):
        return ["rod"]

    def body(self, step, name=None):
        return pv.Line((0, 0.1, 0), (10, 0.1, 0), resolution=100).tube(radius=0.5, n_sides=24)


def test_body_target_centre_at_station():
    centre, axis = body_target(Rod(), None, station=7.0)
    assert axis == "x" and centre == pytest.approx((7.0, 0.1, 0), abs=1e-6)
    views, _ = orbit(centre, radius=3, frames=24, axis=axis, up=(0, 1, 0), span=45)
    assert list(views.values())[0].focal == pytest.approx(centre)
