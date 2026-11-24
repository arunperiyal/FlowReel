"""The axes layer: a triad turning with the camera, arrows at a body end, a ruled box."""
import math

import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.axes import nice_step, outer_edges, tick_text, ticks, triad_viewport
from flowreel.scene.errors import ConfigError
from flowreel.scene.layers import Frame
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.scene.text import to_display
from flowreel.scene.views import parse_view

from tag_fixture import declare_bodies
from test_layer_supports import Riser

PROJECT = "bodies: {riser: {zone: cyl, axis: x, diameter: 2.0}}\n"
VIEWS = {"side": parse_view({"name": "side", "position": [8, 14, 60], "focal": [20, 0, 0]}),
         "top": parse_view({"name": "top", "position": [20, 80, 0.5], "focal": [20, 0, 0],
                            "up": [0, 0, -1]}),
         "oblique": parse_view({"name": "oblique", "position": [-20, 25, 40],
                                "focal": [20, 0, 0], "up": [0, 1, 0]})}


def scene(tmp_path, layer, view="side", size=(320, 180)):
    spec = {"name": "s", "source": "toy", "time": {"frozen": 0, "frames": 1},
            "camera": {"view": view}, "size": [320, 180], "antialias": "none",
            "background": "black", "layers": [{"type": "axes", **layer}]}
    return Scene.make(from_dict(spec, file=str(tmp_path / "s.yml")),
                      declare_bodies(Riser(), PROJECT, tmp_path), VIEWS, size=size)


def drawn(sc, inspect):
    """Draw the layer on a plotter with the frame's camera and call ``inspect`` on it."""
    plotter = pv.Plotter(off_screen=True, window_size=list(sc.size))
    try:
        data = sc.data(0)
        sc.camera.view(0, data).apply(plotter.camera)
        frame = Frame(0, 0, 0.0, data, sc.values(0)[0])
        sc.shot.layers[0].draw(plotter, frame)
        return inspect(plotter, frame)
    finally:
        plotter.close()


def screen_angle(ren, a, b):
    (x0, y0, _), (x1, y1, _) = to_display(ren, a), to_display(ren, b)
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


@pytest.mark.parametrize("view", ["side", "oblique"])
def test_triad_turns_with_the_camera(tmp_path, view):
    def check(plotter, frame):
        rens = plotter.ren_win.GetRenderers()
        triad = rens.GetItemAsObject(rens.GetNumberOfItems() - 1)
        assert triad.GetLayer() == plotter.ren_win.GetNumberOfLayers() - 1 > 1
        focal = np.asarray(plotter.camera.focal_point)
        for e in np.eye(3):
            main = screen_angle(plotter.renderer, focal, focal + 1e-3 * e)
            small = screen_angle(triad, np.zeros(3), e)
            assert abs((main - small + 180) % 360 - 180) < 1.0
        return triad.GetViewport()
    viewport = drawn(scene(tmp_path, {"corner": "upper_right", "size": 90}, view), check)
    assert np.allclose(viewport, triad_viewport("upper_right", 90, (320, 180)))


def test_triad_viewport_and_draft_scaling(tmp_path):
    assert np.allclose(triad_viewport("lower_left", 100, (1000, 500)),
                       (0.01, 0.02, 0.11, 0.22))
    full = scene(tmp_path, {"size": 120, "font_size": 20, "width": 2}).values(0)[0]
    half = scene(tmp_path, {"size": 120, "font_size": 20, "width": 2},
                 size=(160, 90)).values(0)[0]
    assert (half["size"], half["font_size"], half["width"]) == (60, 10, 1)
    assert full["size"] == 120


def test_triad_draws_its_arrows_in_the_corner(tmp_path):
    try:
        img = scene(tmp_path, {}).draw(0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    red = (img[:, :, 0] > 120) & (img[:, :, 1] < 110)
    rows, cols = np.nonzero(red)
    assert red.sum() > 20
    assert rows.min() > 180 - 4 - 110 and cols.max() < 4 + 110          # lower left only


def test_arrows_start_at_a_body_end_sized_in_diameters(tmp_path):
    layer = {"style": "arrows", "origin": {"body": "riser", "end": 1}, "unit": "diameters",
             "length": 3, "axes": ["y", "z"], "labels": ["lift", "span"]}
    sc = scene(tmp_path, layer)
    start, body = sc.shot.layers[0].origin(sc.data(0))
    assert body == "riser" and np.allclose(start, [40, 0, 0], atol=0.05)
    assert sc.shot.layers[0].diameter(sc.data(0), body) == 2.0

    def count(plotter, frame):
        return (len(list(plotter.renderer.GetActors())),
                [a.GetInput() for a in plotter.renderer.GetActors2D()])
    actors, labels = drawn(sc, count)
    assert actors == 2 and labels == ["lift", "span"]


def test_nice_ticks():
    assert nice_step(40) == 10 and nice_step(7) == 1 and nice_step(0.3) == 0.05
    assert nice_step(13) == 2
    assert list(ticks(-1.0, 13.0)) == [0, 2, 4, 6, 8, 10, 12]
    assert list(ticks(0.0, 1.0, 0.25)) == [0, 0.25, 0.5, 0.75, 1.0]
    assert [tick_text(v) for v in (-0.0, 2.5, 10.0)] == ["0", "2.5", "10"]


def test_ruled_rules_the_outer_edges(tmp_path):
    box = {"x": [0, 40], "y": [-3, 3], "z": [-3, 3]}

    def check(plotter, frame):
        ren = plotter.renderer
        rules = sc.shot.layers[0].rulings(plotter, frame)
        mid = np.array([20.0, 0, 0])
        cx, cy, _ = to_display(ren, mid)
        for rule in rules:
            k = rule["axis"]
            fixed, outward = rule["edge"]
            p = fixed.copy()
            p[k] = mid[k]
            x, y, _ = to_display(ren, p)
            others = []
            for si in (-1, 1):
                for sj in (-1, 1):
                    q = mid.copy()
                    i, j = [a for a in range(3) if a != k]
                    q[i] += si * 3 if i else si * 20
                    q[j] += sj * 3 if j else sj * 20
                    others.append(math.hypot(*(np.subtract(to_display(ren, q)[:2], (cx, cy)))))
            assert math.hypot(x - cx, y - cy) == pytest.approx(max(others), abs=1e-6)
            assert np.allclose(np.linalg.norm(outward), 1)
        return rules, [a.GetInput() for a in ren.GetActors2D()]
    sc = scene(tmp_path, {"style": "ruled", "bounds": box, "unit": "diameters", "font_size": 8},
               "oblique")
    rules, labels = drawn(sc, check)
    assert rules[0]["text"] == ["0", "5", "10", "15", "20"]          # 40 long, D = 2
    assert np.allclose(rules[0]["ticks"], [0, 10, 20, 30, 40])
    assert "x / D" in labels and "20" in labels
    sc = scene(tmp_path, {"style": "ruled", "bounds": box, "ticks": 0.5, "font_size": 8},
               "oblique")
    assert drawn(sc, check)[0][1]["text"] == ["-3", "-2.5", "-2", "-1.5", "-1", "-0.5",
                                              "0", "0.5", "1", "1.5", "2", "2.5", "3"]


def test_numbers_do_not_run_into_each_other(tmp_path):
    box = {"x": [0, 40], "y": [-3, 3], "z": [-10, 10]}

    def rules(plotter, frame):
        return {r["axis"]: r for r in sc.shot.layers[0].rulings(plotter, frame)}
    sc = scene(tmp_path, {"style": "ruled", "bounds": box}, "top")
    got = drawn(sc, rules)
    assert sorted(got) == [0, 2]                         # y points at the camera
    assert got[0]["text"] == ["0", "10", "20", "30", "40"]
    assert got[2]["text"] == ["-10", "0", "10"]          # thinned from 5 to 10 apart
    big = scene(tmp_path, {"style": "ruled", "bounds": box, "font_size": 40}, "top")
    assert drawn(big, lambda p, f: [len(r["ticks"]) for r in
                                    big.shot.layers[0].rulings(p, f)]) == [3]   # 0, 20, 40


def test_outer_edges_pick_the_lower_edge_on_a_tie():
    plotter = pv.Plotter(off_screen=True, window_size=[200, 200])
    try:
        plotter.camera.position, plotter.camera.focal_point = (0, 0, 10), (0, 0, 0)
        plotter.camera.up = (0, 1, 0)
        from flowreel.box import Box
        fixed, outward = outer_edges(plotter.renderer, Box((-1, -1, -1), (1, 1, 1)))[0]
        assert fixed[1] == -1 and outward[1] < 0                     # x ruled below
    finally:
        plotter.close()


@pytest.mark.parametrize("layer, msg", [
    ({"style": "triad", "origin": [0, 0, 0]}, "option of style arrows"),
    ({"style": "arrows"}, "missing key 'origin'"),
    ({"style": "arrows", "origin": {"end": 2}}, "expected 0"),
    ({"style": "ruled", "corner": "lower_left"}, "option of style triad"),
    ({"style": "ruled", "ticks": -1}, "must be positive"),
    ({"style": "ruled", "bounds": "box"}, "not allowed"),
    ({"axes": ["x", "x"]}, "twice"),
    ({"axes": ["x", "y"], "labels": ["a"]}, "expected 2 labels"),
    ({"colours": ["#ff0000"]}, "expected 3 colours"),
    ({"unit": "diameters"}, "a triad shows directions"),
    ({"style": "pie"}, "pie"),
])
def test_errors(tmp_path, layer, msg):
    with pytest.raises(ConfigError, match=msg):
        scene(tmp_path, layer)
