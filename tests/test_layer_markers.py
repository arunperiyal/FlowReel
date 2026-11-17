import numpy as np
import pytest
import pyvista as pv

import flowreel.scene.marker_layers  # noqa: F401
from flowreel.box import Box
from flowreel.scene import layers as L
from flowreel.scene.errors import Checker, ConfigError
from tests.conftest import ToySource


def make(kind, **spec):
    return L.build({"type": kind, **spec}, Checker("s.yml", ("layers", 0)))


def frame_for(layer, crop=None, flow=False, src=None):
    src = src or ToySource()
    grid = src.flow(0, ["U", "V", "W"], None) if flow else None
    return L.Frame(0, 0, 0.0, L.FrameData(src, 0, grid, crop), layer.values(0))


def actors_of(layer, **kw):
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, frame_for(layer, **kw))
    out = list(pl.renderer.actors.values())
    pl.close()
    return out


def bounds_of(actor):
    return actor.GetMapper().GetInput().GetBounds()


def test_outline_domain_crop_and_numbers():
    dom = actors_of(make("outline"))[0]
    assert bounds_of(dom) == pytest.approx((-1, 1, -1, 1, 0, 1))
    crop = Box((0, 0, 0), (0.5, 0.5, 0.5))
    assert bounds_of(actors_of(make("outline", bounds="crop"), crop=crop)[0]) == pytest.approx((0, .5, 0, .5, 0, .5))
    assert bounds_of(actors_of(make("outline", bounds="crop"))[0]) == pytest.approx((-1, 1, -1, 1, 0, 1))
    num = make("outline", bounds={"x": [0, 1], "y": [0, 2], "z": [0, 3]})
    assert bounds_of(actors_of(num)[0]) == pytest.approx((0, 1, 0, 2, 0, 3))


def test_outline_width_opacity_tracks_and_errors():
    layer = make("outline", opacity={"from": 0, "to": 1, "frames": [0, 10], "ease": "linear"}, width=3)
    assert layer.values(5)["opacity"] == pytest.approx(0.5)
    a = actors_of(layer)[0]
    assert a.GetProperty().GetLineWidth() == 3 and a.GetProperty().GetOpacity() == 0
    with pytest.raises(ConfigError, match="bounds: 'domian' is not allowed"):
        make("outline", bounds="domian")
    with pytest.raises(ConfigError, match=r"bounds.x: expected \[low, high\]"):
        make("outline", bounds={"x": [1, 0], "y": [0, 1], "z": [0, 1]})


def glyph(**spec):
    return make("glyphs", where={"face": "z-", "grid": [3, 2]}, **spec)


def test_glyph_grid_on_a_face():
    layer = glyph()
    pts = layer.points(frame_for(layer).data)
    assert pts.shape == (6, 3) and (pts[:, 2] == 0).all()
    assert sorted(set(pts[:, 0].round(6))) == pytest.approx([-2 / 3, 0, 2 / 3])
    assert sorted(set(pts[:, 1].round(6))) == pytest.approx([-0.5, 0.5])
    hi = make("glyphs", where={"face": "x+", "grid": [1, 1], "in": {"x": [0, 2], "y": [0, 2], "z": [0, 4]}})
    assert hi.points(frame_for(hi).data)[0] == pytest.approx((2, 1, 2))


def test_glyph_points_and_fixed_direction_draw():
    layer = make("glyphs", where={"points": [[0, 0, 0], [1, 1, 1]]}, direction=[0, 0, 2], size=0.5)
    a = actors_of(layer)[0]
    assert a.GetMapper().GetInput().GetNumberOfPoints() > 0
    assert bounds_of(a)[5] == pytest.approx(1.5)         # tip of the arrow at z = 1 + 0.5


def test_glyph_direction_follows_velocity():
    layer = make("glyphs", where={"points": [[0.5, 0.0, 0.5]]}, direction="velocity", size=1.0)
    assert layer.needs_flow
    a = actors_of(layer, flow=True)[0]
    b = bounds_of(a)
    assert b[3] - b[2] > 0.9 and b[1] - b[0] < 0.3       # solid-body flow at +x is +y


@pytest.mark.parametrize("where, msg", [
    ({"face": "z-"}, "missing key 'grid'"),
    ({"face": "w-", "grid": [2, 2]}, "where.face"),
    ({"face": "z-", "grid": [2]}, "expected \\[n, m\\]"),
    ({"points": [[0, 0]]}, r"points\[0\]: expected 3 numbers"),
    ({"points": [[0, 0, 0]], "face": "z-"}, "either 'face'"),
])
def test_glyph_errors(where, msg):
    with pytest.raises(ConfigError, match=msg):
        make("glyphs", where=where)


def mk(**spec):
    return make("markers3d", at=[1, 2, 3], **spec)


def test_sphere_block_arrow_geometry():
    s = mk(shape="sphere", radius=0.5).mesh(mk(shape="sphere", radius=0.5).values(0))
    assert s.bounds == pytest.approx((0.5, 1.5, 1.5, 2.5, 2.5, 3.5), abs=0.02)
    b = mk(shape="block", size=[2, 4, 6])
    assert b.mesh(b.values(0)).bounds == pytest.approx((0, 2, 0, 4, 0, 6))
    a = mk(shape="arrow3d", direction=[0, 0, 5], length=2.0)
    ab = a.mesh(a.values(0)).bounds
    assert ab[4] == pytest.approx(3) and ab[5] == pytest.approx(5)    # tail at z=3, length 2


def test_marker_moves_with_a_track():
    m = mk(shape="sphere", radius=0.1)
    m = make("markers3d", shape="sphere", radius=0.1,
             at={"from": [0, 0, 0], "to": [10, 0, 0], "frames": [0, 10], "ease": "linear"})
    assert m.values(5)["at"] == pytest.approx((5, 0, 0))
    assert m.mesh(m.values(5)).center == pytest.approx((5, 0, 0), abs=1e-6)


def test_marker_draws_and_errors():
    assert actors_of(mk(shape="block"))
    with pytest.raises(ConfigError, match="shape: .*did you mean 'sphere'"):
        mk(shape="spher")
    with pytest.raises(ConfigError, match="missing key 'at'"):
        make("markers3d", shape="sphere")
    with pytest.raises(ValueError, match="zero vector"):
        z = mk(shape="arrow3d", direction=[0, 0, 0])
        z.mesh(z.values(0))


def geo(**spec):
    return make("geometry", body="grooved_cylinder", **spec)


SMALL = {"span": 4.0, "samples": [41, 81]}


def test_geometry_params_are_tracks_and_build():
    layer = geo(params={**SMALL, "radius": {"from": 0.5, "to": 1.0, "frames": [0, 10], "ease": "linear"}})
    v = layer.values(5)
    assert v["params"]["radius"] == pytest.approx(0.75) and v["params"]["span"] == 4.0
    bounds = layer.mesh(v).bounds
    assert bounds[1] == pytest.approx(4.0, abs=1e-6) and bounds[3] == pytest.approx(0.75, abs=0.01)
    small = layer.mesh(layer.values(0))
    assert small.bounds[3] < bounds[3]


def test_geometry_colour_by_array_draws():
    layer = geo(params=SMALL, colour_by="groove", range=[0, 1])
    assert actors_of(layer)
    assert actors_of(geo(params=SMALL))


@pytest.mark.parametrize("spec, msg", [
    ({"body": "grooved_cylinde"}, "body: 'grooved_cylinde' is not allowed.*did you mean"),
    ({"params": {"radus": 1}}, "params.radus: unknown key.*did you mean 'radius'"),
    ({"params": {"radius": {"from": 1}}}, "params.radius: radius: missing key"),
])
def test_geometry_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        make("geometry", **{"body": "grooved_cylinder", **spec})


def test_markers_and_glyphs_take_a_look_and_arrow_proportions():
    import pyvista as pv
    from flowreel.scene.errors import Checker
    from flowreel.scene import layers as L
    plain = L.build({"type": "markers3d", "shape": "arrow3d", "at": [0, 0, 0]}, Checker())
    thin = L.build({"type": "markers3d", "shape": "arrow3d", "at": [0, 0, 0],
                    "shaft_radius": 0.01, "tip_radius": 0.05, "ambient": 0.5,
                    "specular": 0, "smooth": False}, Checker())
    v0, v1 = plain.values(0), thin.values(0)
    assert (v0["ambient"], v0["specular"], v0["smooth"]) == (0.0, 0.3, True)
    assert plain.mesh(v0).volume > thin.mesh(v1).volume
    glyphs = L.build({"type": "glyphs", "where": {"points": [[0, 0, 0]]}}, Checker())
    assert glyphs.values(0)["specular"] == 0.0                # as before: no highlight
    pl = pv.Plotter(off_screen=True)
    thin.draw(pl, L.Frame(0, 0, 0.0, None, v1))
    actor = next(iter(pl.renderer.actors.values()))
    assert actor.prop.ambient == 0.5 and actor.prop.interpolation.name == "FLAT"
    pl.close()


def test_geometry_blend_markers_and_material():
    import pyvista as pv
    from flowreel.scene.errors import Checker, ConfigError
    from flowreel.scene import layers as L
    spec = {"type": "geometry", "body": "grooved_cylinder", "colour": "#000000",
            "params": {"cut_front": 6.0, "samples": [61, 121]},
            "blend": [{"array": "groove", "colour": "#ff0000", "weight": 0.5},
                      {"array": "fresh", "colour": "#00ff00"}],
            "markers": [{"points": "cutters", "radius": 0.06, "colour": "#ffd08a",
                         "lighting": False}],
            "specular_power": 30, "ambient": 0.18, "sharp_edges": False}
    layer = L.build(spec, Checker())
    v = layer.values(0)
    surf = layer.mesh(v)
    rgb = layer.blend(surf, v)
    floor = np.asarray(surf["groove"]) == 1
    assert (rgb[floor & (np.asarray(surf["fresh"]) == 0)] == [128, 0, 0]).all()   # half red
    assert np.asarray(surf.field_data["cutters"]).shape == (4, 3)
    assert np.allclose(surf.field_data["cutters"][:, 0], 6.0)
    pl = pv.Plotter(off_screen=True)
    layer.draw(pl, L.Frame(0, 0, 0.0, None, v))
    assert len(pl.renderer.actors) == 2                      # the body and the cutters
    pl.close()
    whole = L.build({**spec, "params": {"samples": [61, 121]}}, Checker())
    assert "cutters" not in whole.mesh(whole.values(0)).field_data   # fully carved: none
    with pytest.raises(ConfigError, match="not both"):
        L.build({**spec, "colour_by": "fresh"}, Checker())
    with pytest.raises(ConfigError, match=r"markers\[0\]: missing key 'radius'"):
        L.build({**spec, "markers": [{"points": "cutters"}]}, Checker())
