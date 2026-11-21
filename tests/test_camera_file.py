import pytest

from flowreel.scene.camera_file import HEADER, save_cameras, view_line
from flowreel.scene.camera_path import load_tracks, parse_track
from flowreel.scene.views import View, load_views

VIEWS = {
    "main": View((-19, 13, -5), (6, 0, 8.5), (0, 1, 0), 30.0, name="main"),
    "top": View((6, 40, 9.5), (6, 0, 9.5), (0, 0, -1), parallel=True, parallel_scale=10.6,
                name="top"),
    "odd": View((0.1, 1 / 3, 2e-7), (1, 2, 3), (0, 0, 1), 41.25, name="odd"),
}


def test_round_trip_views_and_tracks(tmp_path):
    tracks = {"carve": parse_track({"frames": 288, "path": "spline", "ease": "in_out",
                                    "keys": [{"frame": 0, "view": "main"},
                                             {"frame": 12.5, "view": "odd"},
                                             {"frame": 218, "view": "main"}]}, VIEWS)}
    path = save_cameras(tmp_path / "cameras.yml", VIEWS, tracks)
    views = load_views(path)
    assert views == VIEWS
    assert load_tracks(path, views) == tracks


def test_layout_reads_as_typed(tmp_path):
    tracks = {"t": parse_track({"keys": [{"frame": 0, "view": "main"},
                                         {"frame": 10, "view": "top"}]}, VIEWS)}
    text = save_cameras(tmp_path / "c.yml", {k: VIEWS[k] for k in ("main", "top")},
                        tracks).read_text()
    assert text == (HEADER + "views:\n"
                    "  - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], "
                    "up: [0, 1, 0], view_angle: 30}\n"
                    "  - {name: top, position: [6, 40, 9.5], focal: [6, 0, 9.5], "
                    "up: [0, 0, -1], parallel: true, parallel_scale: 10.6}\n"
                    "tracks:\n  t:\n    path: linear\n    ease: smooth\n    keys:\n"
                    "      - {frame: 0, view: main}\n      - {frame: 10, view: top}\n")


def test_backup_and_no_tracks(tmp_path):
    path = tmp_path / "cameras.yml"
    path.write_text("# my notes\nviews:\n  - {name: a, position: [0, 0, 1], focal: [0, 0, 0]}\n")
    save_cameras(path, {"main": VIEWS["main"]})
    assert (tmp_path / "cameras.yml.bak").read_text().startswith("# my notes")
    assert "tracks" not in path.read_text()
    assert list(load_views(path)) == ["main"]
    assert not list(tmp_path.glob(".*tmp*"))


def test_view_named_by_its_key_and_quoted(tmp_path):
    views = {"wide, low": VIEWS["main"].with_(name="other"), "yes": VIEWS["top"]}
    out = load_views(save_cameras(tmp_path / "c.yml", views))
    assert list(out) == ["wide, low", "yes"]
    assert out["wide, low"].position == VIEWS["main"].position


def test_track_key_with_unknown_view_is_refused(tmp_path):
    track = parse_track({"keys": [{"frame": 0, "view": "main"}, {"frame": 5, "view": "top"}]},
                        VIEWS)
    with pytest.raises(ValueError, match=r"track 't', key 1 \(frame 5\).*'top'"):
        save_cameras(tmp_path / "c.yml", {"main": VIEWS["main"]}, {"t": track})
    moved = {"main": VIEWS["main"], "top": VIEWS["top"].with_(parallel_scale=2.0)}
    with pytest.raises(ValueError, match="key 1"):
        save_cameras(tmp_path / "c.yml", moved, {"t": track})
    assert not (tmp_path / "c.yml").exists()


def test_no_views_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        save_cameras(tmp_path / "c.yml", {})


def test_view_line_keeps_non_defaults():
    assert "parallel_scale: 2" in view_line(VIEWS["main"].with_(parallel_scale=2.0))
    line = view_line(VIEWS["top"].with_(view_angle=45.0))
    assert "view_angle: 45" in line and "parallel: true" in line


def test_key_eases_round_trip(tmp_path):
    from flowreel.scene.camera_path import build_track
    track = build_track(VIEWS, [(0, "main"), (10, "odd", "hold"), (20, "main")], ease="linear")
    path = save_cameras(tmp_path / "c.yml", VIEWS, {"t": track})
    assert "{frame: 10, view: odd, ease: hold}" in path.read_text()
    assert load_tracks(path, load_views(path))["t"] == track


def test_unnamed_view_found_by_equality(tmp_path):
    from flowreel.scene.camera_path import CameraTrack
    track = CameraTrack(((0, VIEWS["main"].with_(name="")), (5, VIEWS["top"].with_(name=""))))
    text = save_cameras(tmp_path / "c.yml", VIEWS, {"t": track}).read_text()
    assert "{frame: 0, view: main}" in text and "{frame: 5, view: top}" in text


def test_update_adds_and_replaces(tmp_path):
    from flowreel.scene.camera_file import update_cameras
    from flowreel.scene.camera_path import build_track
    path = tmp_path / "cameras.yml"
    update_cameras(path, {"main": VIEWS["main"], "top": VIEWS["top"]})
    moved = VIEWS["main"].with_(view_angle=20.0)
    update_cameras(path, {"main": moved, "odd": VIEWS["odd"]},
                   {"t": build_track(VIEWS, [(0, "odd"), (4, "top")])})
    views = load_views(path)
    assert list(views) == ["main", "top", "odd"] and views["main"].view_angle == 20
    update_cameras(path, tracks={"u": build_track(views, [(0, "main")])})
    assert list(load_tracks(path, load_views(path))) == ["t", "u"]
