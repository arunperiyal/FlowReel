"""Virtual bodies: declared in a tag's domain.yml, built from a shape, attached and driven."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.project.bodies import Attach, parse_bodies
from flowreel.project.names import one_body
from flowreel.scene.errors import Checker, ConfigError
from flowreel.sources.bodies import available_bodies, register_body

from tag_fixture import declare_bodies
from test_layer_supports import Riser          # a riser 40 D long along x, bent 1 D in y

if "stick" not in available_bodies():
    @register_body("stick")
    def stick(length: float = 1.0, width: float = 0.1):
        """A block hanging from the origin: y from -length to 0."""
        return pv.Box(bounds=(-width / 2, width / 2, -length, 0, -width / 2, width / 2))

PROJECT = """\
bodies:
  riser: {zone: cyl, axis: x, diameter: 1.0}
  hanger:
    virtual: true
    shape: stick
    params: {width: 0.2}
    attach: {body: riser, station: 20, offset: [0, -0.5, 0]}
    drive:
      length: {series: stretch, column: L, scale: 2}
    series:
      stretch: data/stretch.csv
"""


@pytest.fixture
def source(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "stretch.csv").write_text("time,L\n0,1\n1,2\n")
    return declare_bodies(Riser(), PROJECT, tmp_path)


def test_the_declaration(source):
    hanger = source.declared["hanger"]
    assert hanger.virtual and hanger.zone is None and hanger.shape == "stick"
    assert hanger.attach == Attach(body="riser", station=20.0, offset=(0.0, -0.5, 0.0))
    assert hanger.drive == {"length": {"series": "stretch", "column": "L", "scale": 2}}
    assert source.bodies() == ["riser", "hanger"]


def test_built_at_the_step_time_on_its_host(source):
    # ToySource step 10 is at time 0.5: L = 1.5, length = 3. The riser's centre at
    # station 20 is (20, 1, 0) (its bend), moved by the offset to (20, 0.5, 0).
    surf = source.body(10, "hanger")
    lo, hi = np.min(surf.points, axis=0), np.max(surf.points, axis=0)
    assert np.allclose([lo[0], hi[0]], [19.9, 20.1], atol=1e-6)
    assert np.isclose(hi[1], 0.5, atol=0.01) and np.isclose(lo[1], 0.5 - 3.0, atol=0.01)
    assert np.isclose(np.ptp(source.body(0, "hanger").points[:, 1]), 2.0)     # L = 1 at t = 0


def test_virtual_bodies_are_not_walls(source):
    assert source.body(0).n_points == source.source.body(0).n_points     # all: real ones only
    assert one_body(source) == "riser"
    with pytest.raises(KeyError, match="'hanger' is virtual: it has no surface zone"):
        source.zone("hanger")


def test_attached_to_a_point_and_by_default():
    bodies = parse_bodies({"p": {"virtual": True, "shape": "stick", "attach": {"point": [1, 2, 3]}},
                           "q": {"virtual": True, "shape": "stick"}}, Checker())
    assert bodies["p"].attach == Attach(point=(1.0, 2.0, 3.0))
    assert bodies["q"].attach == Attach(point=(0.0, 0.0, 0.0))


@pytest.mark.parametrize("spec, msg", [
    ({"virtual": True}, r"p: missing key 'shape'"),
    ({"virtual": True, "shape": "stik"}, r"p\.shape: .*did you mean 'stick'"),
    ({"virtual": "yes", "shape": "stick"}, r"p\.virtual: write virtual: true"),
    ({"virtual": True, "shape": "stick", "zone": "cyl"}, r"p\.zone: unknown key"),
    ({"virtual": True, "shape": "stick", "params": {"lenght": 1}},
     r"p\.params\.lenght: shape 'stick' has no parameter 'lenght' \(parameters: length, width\)"),
    ({"virtual": True, "shape": "stick", "params": {"length": 1}, "drive": {"length": {"series": "s"}}},
     r"p\.drive\.length: is also in params"),
    ({"virtual": True, "shape": "stick", "drive": {"length": 2.0}}, r"p\.drive\.length: expected a series track"),
    ({"virtual": True, "shape": "stick", "drive": {"length": {"series": "s", "scal": 2}}},
     r"p\.drive\.length: .*unknown key 'scal'"),
    ({"virtual": True, "shape": "stick", "attach": {"station": 3}}, r"p\.attach: give body .* or point"),
    ({"virtual": True, "shape": "stick", "attach": {"body": "rizer"}}, r"p\.attach\.body: no body 'rizer'.*'riser'"),
    ({"virtual": True, "shape": "stick", "attach": {"body": "ball", "station": 1}},
     r"p\.attach\.station: 'ball' has no axis"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_bodies({"riser": {"zone": "cyl", "axis": "x"}, "ball": {}, "p": spec}, Checker())


def test_attached_to_another_virtual_body_is_refused():
    with pytest.raises(ConfigError, match=r"p\.attach\.body: 'q' is virtual"):
        parse_bodies({"q": {"virtual": True, "shape": "stick"},
                      "p": {"virtual": True, "shape": "stick", "attach": {"body": "q"}}}, Checker())


# -- drawn as a ghost; no wall --------------------------------------------------------------

from flowreel.scene import flow_layers  # noqa: E402,F401  (registers the layer types)
from flowreel.scene.layers import Frame, FrameData, build  # noqa: E402

PENDULUM = PROJECT + """\
  pendulum:
    virtual: true
    shape: pendulum
    params: {length: 3.0, bob: 0.4}
    attach: {body: riser, station: 20}
"""


@pytest.fixture
def with_pendulum(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "stretch.csv").write_text("time,L\n0,1\n1,2\n")
    return declare_bodies(Riser(), PENDULUM, tmp_path)


def body_layer(spec):
    return build({"type": "body", **spec}, Checker())


def frame_of(layer, source):
    return Frame(0, 0, 0.0, FrameData(source, 0), layer.values(0))


@pytest.mark.parametrize("spec, style", [
    ({"body": "pendulum"}, "ghost"),                     # virtual: ghost by default
    ({"body": "pendulum", "style": "solid"}, "solid"),
    ({"body": "riser"}, "solid"),
    ({"body": ["riser", "pendulum"]}, "solid"),          # not every body drawn is virtual
    ({}, "solid"),                                       # all: the walls
])
def test_virtual_bodies_are_ghosts_by_default(with_pendulum, spec, style):
    layer = body_layer(spec)
    assert layer.style(frame_of(layer, with_pendulum)) == style


def test_a_ghost_is_drawn_with_its_outline(with_pendulum):
    layer = body_layer({"body": "pendulum"})
    plotter = pv.Plotter(off_screen=True)
    try:
        layer.draw(plotter, frame_of(layer, with_pendulum))
        actors = list(plotter.renderer.actors.values())
        assert len(actors) == 2                                    # the body, its outline
        assert actors[0].GetProperty().GetOpacity() == pytest.approx(1 / 3)
    finally:
        plotter.close()


def test_a_virtual_body_has_no_wall(with_pendulum):
    layer = body_layer({"body": "pendulum", "field": "speed"})
    with pytest.raises(ValueError, match="body field 'speed': 'pendulum' is a virtual body"):
        layer.surface(frame_of(layer, with_pendulum))
    iso = build({"type": "iso", "field": "Q", "level": 0.1, "wall_gap": 0.3,
                 "gap_body": "pendulum"}, Checker())
    with pytest.raises(ValueError, match="iso gap_body: 'pendulum' is a virtual body"):
        iso.surface(Frame(0, 0, 0.0, FrameData(with_pendulum, 0), iso.values(0)), iso.values(0))
    sl = build({"type": "slice", "normal": "z", "position": 0.5, "field": "speed",
                "near_wall": [0, 0.5],
                "mask_body": "pendulum"}, Checker())
    plotter = pv.Plotter(off_screen=True)
    try:
        with pytest.raises(ValueError, match="slice mask_body: 'pendulum' is a virtual body"):
            sl.draw(plotter, Frame(0, 0, 0.0, FrameData(with_pendulum, 0), sl.values(0)))
    finally:
        plotter.close()
