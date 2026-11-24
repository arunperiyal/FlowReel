"""Phase 6's check: a new camera track picked in the editor window and rendered.

A scripted session (the window off-screen, driven by the keyboard's own events) picks
the views of ``tests/data/camera/session.yml`` as keys of a new track, with a slip
undone on the way, as a person would. ``flowreel shot render`` then draws the shot on
that track, and its frames are compared with golden frames drawn by
``tools/make_camera_golden.py`` with plain pyvista from the same numbers, without any of
FlowReel's camera code: a key's own view, the view halfway between two keys, and a
nearby frame that must fail.
"""
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from cli_harness import Shell
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

DATA = Path(__file__).parent / "data" / "camera"
SESSION = yaml.safe_load((DATA / "session.yml").read_text())
SHOT = """name: picked
source: geometry:grooved_cylinder
time: {{frozen: 0, frames: {frames}}}
camera: {camera}
size: {size}
antialias: none
layers:
  - {{type: geometry, body: grooved_cylinder, colour: '{colour}', specular: {specular},
     specular_power: {specular_power}, ambient: {ambient}}}
"""


def shot_text(camera: str) -> str:
    b = SESSION["body"]
    return SHOT.format(frames=SESSION["frames"], camera=camera, size=SESSION["size"],
                       colour=b["colour"], specular=b["specular"],
                       specular_power=b["specular_power"], ambient=b["ambient"])


def view(key):
    from flowreel.scene.views import View
    return View(tuple(map(float, key["position"])), tuple(map(float, key["focal"])),
                tuple(map(float, key["up"])), float(key["view_angle"]))


def press(window, k):
    iren = window.plotter.iren.interactor
    iren.SetKeyCode(k)
    iren.SetKeySym(k)
    iren.InvokeEvent("CharEvent")


def pick(folder: Path) -> None:
    """The scripted session: what a person does in the window."""
    from flowreel.editor.scenes import ShotScenes
    from flowreel.editor.state import EditorState
    from flowreel.editor.window import EditorWindow
    from flowreel.scene.rendering import Scene
    from flowreel.scene.views import View
    scenes = ShotScenes(Scene.make(folder / "start.yml"))
    state = EditorState.open(folder / "cameras.yml", "picked", SESSION["frames"], scenes.steps)
    w = EditorWindow(state, scenes, size=(320, 180), off_screen=True)
    try:
        for key in SESSION["keys"]:
            w.set_frame(key["frame"])
            w.look(view(key))
            press(w, "s")
        w.set_frame(18)                                  # a slip: a key too many ...
        w.look(View((0, -3, 2), (6, 0, 0), (0, 0, 1)))
        press(w, "s")
        press(w, "u")                                    # ... taken back
        w.set_frame(23)
        press(w, "r")                                    # the last key replaced ...
        press(w, "u")                                    # ... and put back
        press(w, "p")
    finally:
        w.plotter.close()


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    folder = tmp_path_factory.mktemp("camera")
    (folder / "flowreel.yml").write_text("")                # a project (docs/guide/projects/project.md)
    first = SESSION["keys"][0]
    (folder / "cameras.yml").write_text(
        "views:\n  - {name: start, position: %s, focal: %s, up: %s, view_angle: %s}\n"
        % (first["position"], first["focal"], first["up"], first["view_angle"]))
    (folder / "start.yml").write_text(shot_text("{view: start}"))
    (folder / "picked.yml").write_text(shot_text("{track: picked}"))
    try:
        pick(folder)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    sh = Shell(folder / "store")
    status, _, err = sh.run(f"shot render {folder / 'picked.yml'} --frames 0:12 -j 2 "
                            f"-o {folder / 'frames'}")
    if status and ("OpenGL" in err or "display" in err.lower()):
        pytest.skip(f"off-screen rendering is not available: {err}")
    assert status == 0, err
    return folder


def picture(folder, i):
    return np.asarray(Image.open(folder / "frames" / "picked" / f"frame_{i:05d}.png").convert("RGB"))


def test_the_session_wrote_the_picked_keys(session):
    from flowreel.scene.camera_path import load_tracks
    from flowreel.scene.views import load_views
    views = load_views(session / "cameras.yml")
    track = load_tracks(session / "cameras.yml", views)["picked"]
    assert [k[0] for k in track.keys] == [k["frame"] for k in SESSION["keys"]]
    for (_, got), key in zip(track.keys, SESSION["keys"]):
        assert got.with_(name="") == view(key)
    assert "picked_0018" not in views and track.frames == SESSION["frames"]


@pytest.mark.parametrize("which", ["key", "mid"])
def test_rendered_frames_match_their_goldens(session, which):
    golden = np.asarray(Image.open(DATA / f"golden_{which}.png").convert("RGB"))
    got = picture(session, SESSION["golden"][which])
    assert got.shape == golden.shape == (360, 640, 3)
    mean, clear = difference(got, golden)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (which, mean, clear)


def test_a_nearby_frame_fails_the_same_limits(session):
    golden = np.asarray(Image.open(DATA / "golden_mid.png").convert("RGB"))
    mean, clear = difference(picture(session, SESSION["golden"]["near"]), golden)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (mean, clear)
