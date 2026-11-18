"""Under a shot's stretch, symbols, arrows and ticks keep their shape; labels go where
the stretched model is drawn."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.drawn import drawing, keep_shape, scale_of, to_drawn
from flowreel.scene.text import to_display


def test_scale_is_known_only_while_drawing():
    plotter = pv.Plotter(off_screen=True)
    try:
        ren = plotter.renderer
        assert np.all(scale_of(ren) == 1)
        with drawing(ren, (0.02, 1, 1)):
            assert np.allclose(scale_of(ren), (0.02, 1, 1))
            assert np.allclose(to_drawn(ren, (500, 2, 3)), (10, 2, 3))
        assert np.all(scale_of(ren) == 1)
        with drawing(ren, None):
            assert np.all(scale_of(ren) == 1)
    finally:
        plotter.close()


def test_keep_shape_undoes_the_stretch_about_the_anchor():
    plotter = pv.Plotter(off_screen=True)
    try:
        ren = plotter.renderer
        cone = pv.Cone(center=(500, 0, 0), direction=(1, 0, 0), height=2, radius=1)
        size = np.ptp(cone.points, axis=0)
        with drawing(ren, (0.02, 1, 1)):
            kept = keep_shape(ren, cone.copy(), (500, 0, 0))
        drawn = kept.points * (0.02, 1, 1)             # what the actor's scale draws
        assert np.allclose(np.ptp(drawn, axis=0), size)
        anchor = np.array([500.0, 0, 0])                  # drawn at 10, offsets true size
        assert np.allclose(drawn.mean(axis=0),
                           anchor * (0.02, 1, 1) + cone.points.mean(axis=0) - anchor, atol=1e-4)
        same = keep_shape(ren, cone.copy(), (500, 0, 0))
        assert np.allclose(same.points, cone.points)
    finally:
        plotter.close()


def test_labels_fall_where_the_stretched_model_is():
    plotter = pv.Plotter(off_screen=True, window_size=[200, 100])
    try:
        plotter.camera.position, plotter.camera.focal_point = (5, 0, 20), (5, 0, 0)
        ren = plotter.renderer
        at_ten = to_display(ren, (10, 0, 0))
        with drawing(ren, (0.02, 1, 1)):
            assert np.allclose(to_display(ren, (500, 0, 0)), at_ten)
    finally:
        plotter.close()


def test_span_shot_symbols_keep_their_size(tmp_path):
    """The supports of a stretched beam: a symbol is a diameter or so wide, drawn."""
    from flowreel.scene.layers import Frame
    from flowreel.scene.rendering import Scene
    from flowreel.scene.shot import from_dict
    from flowreel.scene.views import parse_view
    from test_layer_supports import PROJECT, Riser
    (tmp_path / "flowreel.yml").write_text(PROJECT)
    shot = from_dict({"name": "s", "source": "toy:none", "time": {"frozen": 0, "frames": 1},
                      "camera": {"view": "v"}, "size": [320, 180], "antialias": "none",
                      "stretch": {"x": 0.1},
                      "layers": [{"type": "supports", "ends": [0]}]}, file=str(tmp_path / "s.yml"))
    sc = Scene.make(shot, Riser(), {"v": parse_view({"name": "v", "position": [2, 0, 30],
                                                      "focal": [2, 0, 0]})})
    plotter = pv.Plotter(off_screen=True, window_size=[320, 180])
    try:
        sc.camera.view(0, sc.data(0)).apply(plotter.camera)
        with drawing(plotter.renderer, (0.1, 1, 1)):
            sc.shot.layers[0].draw(plotter, Frame(0, 0, 0.0, sc.data(0), sc.values(0)[0]))
        widths = []
        for actor in plotter.renderer.actors.values():
            actor.SetScale(0.1, 1, 1)
            lo_x, hi_x = actor.GetBounds()[:2]
            widths.append(hi_x - lo_x)
    finally:
        plotter.close()
    assert widths and max(widths) == pytest.approx(1.0, rel=0.6)    # not a tenth of it
    assert max(widths) > 0.5
