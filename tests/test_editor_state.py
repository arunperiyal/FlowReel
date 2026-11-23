"""The camera editor's state, without a window: keys collected, written at once."""
import pytest

from flowreel.editor.state import EditorState
from flowreel.scene.camera_path import load_tracks
from flowreel.scene.views import View, load_views


def v(x):
    return View((x, 0, 10), (x, 0, 0), view_angle=30)


def read(path):
    views = load_views(path)
    return views, load_tracks(path, views)


def test_save_writes_at_once_and_names_by_frame(tmp_path):
    path = tmp_path / "cameras.yml"
    s = EditorState.open(path, "pan", frames=48, steps=[0, 10])
    assert not path.exists() and s.play() == []
    s.set_frame(0)
    assert s.save(v(0)) == "pan_0000"
    s.set_frame(30)
    s.save(v(3))
    views, tracks = read(path)
    assert sorted(views) == ["pan_0000", "pan_0030"]
    t = tracks["pan"]
    assert [k[0] for k in t.keys] == [0, 30] and t.frames == 48
    assert t.at(15).position == pytest.approx((1.5, 0, 10), abs=0.5)
    assert len(s.play()) == 48 and s.play()[47].position == (3, 0, 10)


def test_save_at_a_keyed_frame_replaces_it_and_undo_goes_back(tmp_path):
    path = tmp_path / "cameras.yml"
    s = EditorState.open(path, "pan", frames=20, steps=[0])
    s.save(v(0))
    s.save(v(1))                                     # same frame: replaced
    assert len(s.keys) == 1 and s.keys[0].position == (1, 0, 10)
    assert s.undo() and read(path)[0]["pan_0000"].position == (0, 0, 10)
    assert s.undo() and not s.keys
    assert not path.exists() and (tmp_path / "cameras.yml.bak").exists()   # nothing left
    assert not s.undo()


def test_replace_nearest_keeps_its_frame(tmp_path):
    s = EditorState.open(tmp_path / "c.yml", "pan", frames=100, steps=[0])
    for f in (0, 40, 90):
        s.set_frame(f)
        s.save(v(f))
    s.set_frame(70)
    assert s.replace(v(-1)) == 90                    # 90 is nearer than 40
    assert s.keys[90].position == (-1, 0, 10) and sorted(s.keys) == [0, 40, 90]
    s.set_frame(65)
    assert s.replace(v(-2)) == 40                    # 25 frames from both: the earlier
    assert EditorState.open(tmp_path / "e.yml", "t", 5, [0]).replace(v(0)) is None


def test_other_views_and_tracks_are_kept_and_a_track_is_taken_up(tmp_path):
    path = tmp_path / "cameras.yml"
    path.write_text(
        "views:\n  - {name: main, position: [0, 0, 5], focal: [0, 0, 0]}\n"
        "  - {name: top, position: [0, 9, 0], focal: [0, 0, 0], up: [0, 0, -1]}\n"
        "tracks:\n  old: {keys: [{frame: 0, view: main}, {frame: 9, view: top}]}\n"
        "  pan: {path: spline, keys: [{frame: 0, view: main}, {frame: 12, view: top}]}\n")
    s = EditorState.open(path, "pan", frames=24, steps=[0])
    assert sorted(s.keys) == [0, 12] and s.path_kind == "spline"
    assert s.shared == {"main", "top"}
    s.set_frame(12)
    s.replace(v(7))                                  # 'top' is old's too: a view of its own
    views, tracks = read(path)
    assert views["top"].position == (0, 9, 0)        # untouched
    assert views["pan_0012"].position == (7, 0, 10)
    assert tracks["old"].keys[1][1] == views["top"]
    assert tracks["pan"].path == "spline" and tracks["pan"].keys[1][1] == views["pan_0012"]


def test_steps_and_frames(tmp_path):
    s = EditorState.open(tmp_path / "c.yml", "pan", frames=10, steps=[100, 200, 300])
    assert s.step == 100 and s.next_step() == 200 and s.next_step() == 300
    assert s.next_step() == 100 and s.set_step(9) == 300
    s.set_frame(99)
    assert s.frame == 9
    s.set_frame(-3)
    assert s.frame == 0
    assert s.status() == "track pan: 0 views saved   frame 0 of 9   step 300"
    with pytest.raises(ValueError, match="frames"):
        EditorState.open(tmp_path / "c.yml", "pan", frames=0, steps=[0])
    with pytest.raises(ValueError, match="time step"):
        EditorState.open(tmp_path / "c.yml", "pan", frames=5, steps=[])


def test_the_frame_shows_its_step_when_the_steps_of_frames_are_known(tmp_path):
    s = EditorState.open(tmp_path / "c.yml", "pan", frames=30, steps=[0, 10],
                         frame_steps=[0] * 10 + [10] * 10)
    assert s.set_frame(12) and s.step == 10
    assert not s.set_frame(13) and s.step == 10          # the same step: nothing moves
    assert s.set_frame(3) and s.step == 0
    assert s.set_frame(25) and s.step == 10              # past the shot: its last frame's
    s.set_step(0)                                          # the step slider still moves alone
    assert s.step == 0 and s.frame == 25


def test_without_the_steps_of_frames_the_frame_leaves_the_step(tmp_path):
    s = EditorState.open(tmp_path / "c.yml", "pan", frames=30, steps=[0, 10])
    s.set_step(1)
    assert not s.set_frame(5) and s.step == 10


def test_the_frames_with_a_key(tmp_path):
    s = EditorState.open(tmp_path / "c.yml", "pan", frames=48, steps=[0])
    assert s.key_frames() == []
    for frame in (30, 0, 12):
        s.set_frame(frame)
        s.save(v(frame))
    assert s.key_frames() == [0, 12, 30]
    s.undo()
    assert s.key_frames() == [0, 30]
