"""The camera editor's window, off-screen, driven by synthetic key events."""
import numpy as np
import pytest

from flowreel.editor.scenes import ShotScenes
from flowreel.editor.state import EditorState
from flowreel.editor.window import EditorWindow
from flowreel.scene.camera_path import load_tracks
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.scene.views import View, load_views, parse_view

VIEWS = {"main": parse_view({"name": "main", "position": [3, 2, 4], "focal": [0, 0, 0.5]})}


def shot(**extra):
    spec = {"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [160, 90], "antialias": "none",
            "layers": [{"type": "body", "colour": "#ff0000"},
                       {"type": "slice", "normal": "z", "position": 0.5, "field": "speed",
                        "range": [0, 2]}]}
    spec.update(extra)
    return from_dict(spec, file="toy.yml")


@pytest.fixture
def window(tmp_path, toy_source):
    scene = Scene.make(shot(), toy_source, VIEWS, {}, (160, 90))
    scenes = ShotScenes(scene)
    state = EditorState.open(tmp_path / "cameras.yml", "picked", frames=30, steps=scenes.steps)
    try:
        w = EditorWindow(state, scenes, size=(320, 180), off_screen=True,
                         anchors=[("centre", (0, 0, 0.5))])
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    yield w
    w.plotter.close()


def key(w, k):
    """Send character ``k`` to the window as the keyboard would."""
    iren = w.plotter.iren.interactor
    iren.SetKeyCode(k)
    iren.SetKeySym(k)
    iren.InvokeEvent("CharEvent")


def picture(w, scene_only=False):
    p = np.asarray(w.plotter.screenshot(return_img=True))[:, :, :3].astype(int)
    return p[50:140, 170:310] if scene_only else p      # clear of the text and widgets


def test_opens_at_the_shots_camera_with_the_first_step(window):
    assert window.view().position == pytest.approx(VIEWS["main"].position)
    assert window.state.steps == [0, 10, 20] and window.cache.shown == 0
    red = picture(window)
    assert ((red[..., 0] > 150) & (red[..., 1] < 80)).mean() > 0.002      # the body


def test_keys_save_replace_undo_and_play(window, tmp_path):
    w = window
    key(w, "s")
    assert w.message == "saved picked_0000 at frame 0"
    w.set_frame(29)
    w.look(View((0, -4, 2), (0, 0, 0.5), (0, 0, 1)))
    key(w, "s")
    views = load_views(tmp_path / "cameras.yml")
    track = load_tracks(tmp_path / "cameras.yml", views)["picked"]
    assert [k[0] for k in track.keys] == [0, 29] and track.frames == 30
    assert views["picked_0029"].position == pytest.approx((0, -4, 2))
    w.set_frame(20)
    w.look(View((0, -5, 2), (0, 0, 0.5), (0, 0, 1)))
    key(w, "r")                                      # nearest key: 29
    assert w.message == "replaced the view at frame 29"
    assert load_views(tmp_path / "cameras.yml")["picked_0029"].position == pytest.approx((0, -5, 2))
    key(w, "u")
    assert load_views(tmp_path / "cameras.yml")["picked_0029"].position == pytest.approx((0, -4, 2))
    here = w.view()
    key(w, "p")
    assert w.message == "played 30 frames" and w.view() == here


def test_vtk_keys_of_ours_are_switched_off(window):
    w = window
    w.look(View((0, -4, 2), (0, 0, 0.5), (0, 0, 1)))
    key(w, "r")                                      # VTK would reset the camera
    assert w.view().position == pytest.approx((0, -4, 2))
    assert w.message == "no view to replace yet: s saves one"


def test_steps_are_built_once(window):
    w = window
    first = picture(w, True)
    key(w, "n")
    assert w.cache.shown == 10 and w.message.startswith("step 10 loaded in")
    w.set_step(0)
    assert w.message == "step 0" and np.abs(picture(w, True) - first).max() == 0
    w.set_step(1)
    assert w.message == "step 10"                    # kept: not built again
    assert sorted(w.cache.actors) == [0, 10]
    assert not np.array_equal(picture(w, True), first)   # the vortex is faster at step 10


def test_anchor_markers_are_drawn(window):
    assert any("anchors" in name for name in window.plotter.actors)


def test_the_step_slider_follows_the_keys(window):
    key(window, "n")
    rep = window._step_slider.GetRepresentation()
    assert rep.GetValue() == 1 and rep.GetTitleText() == "Time step 10 (2 of 3)"


class Stretched:
    """A scene source with no data: one step, a sphere, drawn stretched 2x along x."""

    steps = [0]
    stretch = (2.0, 1.0, 1.0)
    first_view = View((0, -6, 0), (0, 0, 0), (0, 0, 1))

    def build(self, plotter, step):
        import pyvista as pv
        plotter.add_mesh(pv.Sphere(radius=0.2), color="white")


def test_markers_sit_on_the_stretched_model(tmp_path):
    state = EditorState.open(tmp_path / "c.yml", "t", 5, [0])
    try:
        w = EditorWindow(state, Stretched(), size=(160, 90), off_screen=True,
                         anchors=[("tip", (1.0, 0.0, 0.5))])
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    try:
        points = []
        for name, actor in w.plotter.actors.items():
            mapper = getattr(actor, "GetMapper", lambda: None)()
            if "anchors" not in name or mapper is None:
                continue
            if mapper.GetInputAlgorithm() is not None:
                mapper.GetInputAlgorithm().Update()
            data = mapper.GetInputDataObject(0, 0)
            if data is not None and hasattr(data, "GetPoint") and data.GetNumberOfPoints():
                points.append(data.GetPoint(0))
        assert points and points[0] == pytest.approx((2.0, 0.0, 0.5))
    finally:
        w.plotter.close()


def test_the_frame_slider_follows_set_frame(window):
    window.set_frame(17.6)
    assert window.state.frame == 18
    assert window._frame_slider.GetRepresentation().GetValue() == 18


def test_a_perspective_view_is_saved_without_vtks_parallel_scale(window, tmp_path):
    window.plotter.camera.parallel_scale = 6.5
    key(window, "s")
    assert window.view().parallel_scale == 1.0
    assert "parallel_scale" not in (tmp_path / "cameras.yml").read_text()


def test_ticks_fall_along_the_frame_slider():
    from flowreel.editor.window import FRAME_A, FRAME_B, tick_positions
    assert tick_positions([0, 29], 30) == pytest.approx([FRAME_A[0], FRAME_B[0]])
    assert tick_positions([10], 21) == pytest.approx([(FRAME_A[0] + FRAME_B[0]) / 2])
    assert tick_positions([0], 1) == []


def test_saved_keys_are_marked_on_the_frame_slider(window):
    assert getattr(window, "_tick_actor", None) is None
    for frame in (0, 20):
        window.set_frame(frame)
        key(window, "s")
    lines = window._tick_actor.GetMapper().GetInput()
    assert lines.GetNumberOfLines() == 2
    key(window, "u")
    assert window._tick_actor.GetMapper().GetInput().GetNumberOfLines() == 1


def test_the_frame_slider_moves_the_step_slider(tmp_path, toy_source):
    scene = Scene.make(shot(), toy_source, VIEWS, {}, (160, 90))    # one frame a step
    scenes = ShotScenes(scene)
    state = EditorState.open(tmp_path / "cameras.yml", "picked", frames=len(scenes.frame_steps),
                             steps=scenes.steps, frame_steps=scenes.frame_steps)
    try:
        w = EditorWindow(state, scenes, size=(320, 180), off_screen=True)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    try:
        last = len(scenes.frame_steps) - 1
        w.set_frame(last)
        assert state.step == scenes.frame_steps[last] == 20
        assert w._step_slider.GetRepresentation().GetValue() == state.step_index
        w.set_frame(0)
        assert state.step == 0
    finally:
        w.plotter.close()
