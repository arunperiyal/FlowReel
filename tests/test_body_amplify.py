"""amplify on a body layer: the displacement from rest drawn larger, never with flow."""
import numpy as np
import pytest

from flowreel.scene.errors import ConfigError
from flowreel.scene.layers import Frame
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict

from test_layer_centreline import VIEWS, Swinging     # bent 1, -1, 0.5 D at steps 0, 10, 20


def shot(layers, **time):
    spec = {"name": "s", "source": "toy", "time": time or {"steps": [0, 20]},
            "camera": {"view": "side"}, "size": [64, 48], "layers": layers}
    return from_dict(spec, file="nowhere/s.yml")


def drawn(sc, index):
    layer = sc.shot.layers[0]
    frame = Frame(index, sc.plan.time.step(index), 0.0, sc.data(index), sc.values(index)[0])
    return layer.amplified(frame, layer.surface(frame))


def mid_y(surface):
    pts = np.asarray(surface.points)
    return pts[np.abs(pts[:, 0] - 20) < 0.05, 1].mean()


def test_amplify_scales_the_displacement_from_rest():
    sc = Scene.make(shot([{"type": "body", "amplify": 3}]), Swinging(), VIEWS)
    assert mid_y(drawn(sc, 0)) == pytest.approx(1.0, abs=1e-6)        # the rest step itself
    assert mid_y(drawn(sc, 1)) == pytest.approx(1 + 3 * (-1 - 1), abs=1e-6)   # -5
    plain = Scene.make(shot([{"type": "body"}]), Swinging(), VIEWS)
    assert mid_y(drawn(plain, 1)) == pytest.approx(-1.0, abs=1e-6)


def test_rest_step_and_its_check():
    sc = Scene.make(shot([{"type": "body", "amplify": 2, "rest_step": 20}]), Swinging(), VIEWS)
    assert mid_y(drawn(sc, 1)) == pytest.approx(0.5 + 2 * (-1 - 0.5), abs=1e-6)
    with pytest.raises(ConfigError, match=r"layers\[0\]\.rest_step: expected a whole number"):
        shot([{"type": "body", "amplify": 2, "rest_step": "first"}])


def test_refused_with_flow_layers_but_not_on_a_centreline():
    with pytest.raises(ConfigError, match=r"layers\[1\]\.amplify: a body drawn amplified would "
                                          r"not match the flow of layers\[0\] \(iso\)"):
        shot([{"type": "iso", "field": "Q", "level": 0.1}, {"type": "body", "amplify": 10}])
    with pytest.raises(ConfigError, match=r"\(glyphs\)"):
        shot([{"type": "body", "amplify": 10},
              {"type": "glyphs", "where": {"points": [[0, 0, 0]]}, "direction": "velocity"}])
    shot([{"type": "iso", "field": "Q", "level": 0.1}, {"type": "centreline", "amplify": 50}])
    shot([{"type": "iso", "field": "Q", "level": 0.1}, {"type": "body", "amplify": 1}])  # no-op
