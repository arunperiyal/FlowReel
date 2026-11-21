"""Surfaces saved for the camera editor, and opened again without the data."""
import json

import numpy as np
import pytest
import pyvista as pv

from flowreel.editor.surfaces import (SCENE_FILE, SavedScenes, load_surfaces, save_shot_surfaces,
                                      save_surfaces, step_folder)
from flowreel.scene.shot import from_dict
from flowreel.scene.views import parse_view

VIEWS = {"main": parse_view({"name": "main", "position": [3, 2, 4], "focal": [0, 0, 0.5]})}


def shot(**extra):
    spec = {"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [160, 90], "antialias": "none",
            "background": "#102030",
            "layers": [{"type": "body", "colour": "#ff0000"},
                       {"type": "slice", "normal": "z", "position": 0.5, "field": "speed",
                        "range": [0, 2]},
                       {"type": "outline", "bounds": "domain", "colour": "#88aacc"}]}
    spec.update(extra)
    return from_dict(spec, file="toy.yml")


def shoot(build, view):
    p = pv.Plotter(off_screen=True, window_size=(160, 90))
    try:
        build(p)
        view.apply(p.camera)
        p.renderer.ResetCameraClippingRange()
        return np.asarray(p.screenshot(return_img=True))[:, :, :3].astype(int)
    finally:
        p.close()


def test_a_scene_comes_back_looking_as_it_was(tmp_path):
    s = pv.Sphere(radius=0.3)
    s["z"] = s.points[:, 2]
    cube = pv.Cube(center=(0.8, 0, 0), x_length=0.4, y_length=0.4, z_length=0.4)
    cube.cell_data["k"] = np.arange(cube.n_cells, dtype=float)

    def original(p):
        p.add_mesh(s, scalars="z", cmap="viridis", show_scalar_bar=False)
        a = p.add_mesh(cube, scalars="k", cmap="plasma", show_scalar_bar=False)
        a.SetScale(1, 2, 1)
        p.add_mesh(pv.Line((-1, -0.5, 0), (1, -0.5, 0)), color="#33ff66", line_width=3,
                   opacity=0.7)

    view = parse_view({"position": [0, -3, 1.5], "focal": [0.2, 0, 0]})
    first = []

    def keep(p):
        original(p)
        p.render()
        first.append(save_surfaces(p, tmp_path / "s"))

    before = shoot(keep, view)
    assert first == [3]
    record = json.loads((tmp_path / "s" / SCENE_FILE).read_text())["actors"]
    assert [r["colours"] for r in record] == ["point", "cell", None]
    assert record[1]["scale"] == [1, 2, 1] and record[2]["look"]["Opacity"] == pytest.approx(0.7)
    after = shoot(lambda p: load_surfaces(p, tmp_path / "s"), view)
    assert np.abs(before - after).mean() < 2.0          # grey levels, of 255


def test_a_shots_steps_saved_and_opened(tmp_path, toy_source):
    try:
        steps = save_shot_surfaces(shot(), tmp_path / "vtp", source=toy_source, views=VIEWS)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert steps == [0, 10, 20]
    assert len(list(step_folder(tmp_path / "vtp", 10).glob("actor_*"))) == 3
    saved = SavedScenes(tmp_path / "vtp")
    assert saved.steps == [0, 10, 20]
    assert saved.first_view.position == pytest.approx(VIEWS["main"].position)
    assert saved.background == pytest.approx((0x10 / 255, 0x20 / 255, 0x30 / 255))
    assert save_shot_surfaces(shot(), tmp_path / "two", steps=[20], source=toy_source,
                              views=VIEWS) == [20]
    with pytest.raises(ValueError, match=r"steps \[5\] are not in the shot"):
        save_shot_surfaces(shot(), tmp_path / "x", steps=[5], source=toy_source, views=VIEWS)


def test_the_editor_opens_saved_surfaces(tmp_path, toy_source):
    from flowreel.editor.state import EditorState
    from flowreel.editor.window import EditorWindow
    try:
        save_shot_surfaces(shot(), tmp_path / "vtp", source=toy_source, views=VIEWS)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    saved = SavedScenes(tmp_path / "vtp")
    state = EditorState.open(tmp_path / "cameras.yml", "t", 10, saved.steps)
    w = EditorWindow(state, saved, size=(320, 180), off_screen=True)
    try:
        w.press("n")
        assert w.cache.shown == 10 and len(w.cache.actors[10]) == 3
        w.press("s")
        assert (tmp_path / "cameras.yml").is_file()
    finally:
        w.plotter.close()


def test_missing_surfaces(tmp_path):
    with pytest.raises(FileNotFoundError, match="--save-vtp"):
        SavedScenes(tmp_path)
    with pytest.raises(FileNotFoundError, match="no saved surfaces"):
        load_surfaces(pv.Plotter(off_screen=True), tmp_path)
