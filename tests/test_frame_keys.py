"""Frame keys: a frame is drawn again only when something that reaches it changed."""
import numpy as np
import pytest

from flowreel.scene import render
from flowreel.scene.keys import KeyStore, code_version, digest, frame_key
from flowreel.scene.rendering import Scene

from test_render import VIEWS, toy_shot


def run(shot, source, out, **kw):
    try:
        return render(shot, source=source, views=VIEWS, out=out, processes=False, **kw)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")


def statuses(report):
    return [f.status for f in report.frames]


def test_a_second_render_skips_every_frame(toy_source, tmp_path):
    assert statuses(run(toy_shot(), toy_source, tmp_path)) == ["rendered"] * 3
    assert statuses(run(toy_shot(), toy_source, tmp_path)) == ["skipped"] * 3
    assert statuses(run(toy_shot(), toy_source, tmp_path, force=True)) == ["rendered"] * 3


def test_only_frames_whose_values_changed_are_drawn(toy_source, tmp_path):
    run(toy_shot(), toy_source, tmp_path)
    colour = {"keys": [[0, "#ff0000"], [1, "#ff0000"], [2, "#00ff00"]]}
    shot = toy_shot(layers=[{"type": "body", "colour": colour},
                            {"type": "outline", "bounds": "domain"}])
    assert statuses(run(shot, toy_source, tmp_path)) == ["skipped", "skipped", "rendered"]


def test_a_missing_file_or_key_is_drawn_again(toy_source, tmp_path):
    report = run(toy_shot(), toy_source, tmp_path)
    report.frames[0].path.unlink()
    store = KeyStore(report.folder)
    store.put("frame_00001.png", "stale")
    assert statuses(run(toy_shot(), toy_source, tmp_path)) == ["rendered", "rendered", "skipped"]


def test_keys_follow_what_reaches_the_picture(toy_source):
    base = Scene.make(toy_shot(), toy_source, VIEWS)
    key = frame_key(base, 0)
    assert frame_key(Scene.make(toy_shot(), toy_source, VIEWS), 0) == key
    assert frame_key(base, 1) != key                                   # another step
    assert frame_key(Scene.make(toy_shot(camera={"view": "side"}), toy_source, VIEWS), 0) != key
    assert frame_key(Scene.make(toy_shot(background="white"), toy_source, VIEWS), 0) != key
    assert frame_key(Scene.make(toy_shot(), toy_source, VIEWS, size=(32, 24)), 0) != key
    assert frame_key(Scene.make(toy_shot(name="other"), toy_source, VIEWS), 0) == key


def test_digest_is_canonical():
    assert digest({"a": np.array([1.0, 2.0]), "b": (1, 2)}) == digest({"b": [1, 2], "a": [1.0, 2.0]})
    assert len(code_version()) == 16 and code_version("fields") != code_version()
