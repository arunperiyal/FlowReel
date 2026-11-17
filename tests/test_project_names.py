"""Body names through flowreel.yml: layers, follow and keys use the declared names."""
import pickle

import pytest
import pyvista as pv

from flowreel.project import PROJECT_FILE, Project
from flowreel.project.bodies import Body
from flowreel.project.names import DeclaredSource, declare, one_body
from flowreel.scene.camera import ShotCamera
from flowreel.scene.errors import Checker
from flowreel.scene.keys import frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict

from conftest import ToySource
from test_render import VIEWS


class TwoBodies(ToySource):
    """The toy flow with two small spheres, zones ``cyl`` (z = 0.3) and ``cyl2`` (z = 0.7)."""

    name = "two"
    CENTRES = {"cyl": 0.3, "cyl2": 0.7}

    def bodies(self):
        return list(self.CENTRES)

    def body(self, step, name=None):
        names = self.bodies() if name is None else [name]
        if any(n not in self.CENTRES for n in names):
            raise KeyError(name)
        return pv.merge([pv.Sphere(radius=0.1, center=(0, 0, self.CENTRES[n])) for n in names])


DECLARED = {"riser": Body("riser", "cyl", axis="z")}


def z_of(surface):
    return round(float(surface.center[2]), 3)


def test_declared_names_read_their_zone():
    src = DeclaredSource(TwoBodies(), DECLARED)
    assert src.bodies() == ["riser", "cyl2"]                 # declared, then unclaimed zones
    assert z_of(src.body(0, "riser")) == 0.3
    assert z_of(src.body(0, "cyl")) == 0.3 and z_of(src.body(0, "cyl2")) == 0.7
    assert z_of(src.body(0)) == 0.5                          # every body without a name
    assert src.steps() == [0, 10, 20] and src.name == "two"   # the rest is the source's
    assert src.declaration("cyl") is DECLARED["riser"] and src.declaration("cyl2") is None


def test_unknown_names_say_what_there_is():
    src = DeclaredSource(TwoBodies(), DECLARED)
    with pytest.raises(KeyError, match=r"no body 'risr' \(bodies: riser, cyl2\); did you mean 'riser'"):
        src.body(0, "risr")
    bad = DeclaredSource(TwoBodies(), {"riser": Body("riser", "pipe")})
    with pytest.raises(KeyError, match=r"declared as zone 'pipe', which two does not have"):
        bad.body(0, "riser")


def test_one_body_when_the_name_is_left_out():
    assert one_body(DeclaredSource(TwoBodies(), DECLARED)) == "riser"
    assert one_body(ToySource()) == "sphere"
    with pytest.raises(LookupError, match="name the body: two has cyl, cyl2"):
        one_body(TwoBodies())
    both = {"a": Body("a", "cyl"), "b": Body("b", "cyl2")}
    with pytest.raises(LookupError, match="name the body: two has a, b"):
        one_body(DeclaredSource(TwoBodies(), both))


def test_declare_and_pickle():
    plain = TwoBodies()
    assert declare(plain, None) is plain and declare(plain, Project()) is plain
    src = declare(plain, Project(bodies=DECLARED))
    assert declare(src, Project(bodies=DECLARED)) is src
    again = pickle.loads(pickle.dumps(src))
    assert isinstance(again, DeclaredSource) and z_of(again.body(0, "riser")) == 0.3


def shot_in(folder, project: str | None, camera=None, body="riser"):
    if project is not None:
        (folder / PROJECT_FILE).write_text(project)
    spec = {"name": "two", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": camera or {"view": "main"}, "size": [64, 48], "antialias": "none",
            "layers": [{"type": "body", "body": body}]}
    return from_dict(spec, file=str(folder / "two.yml"))


def test_a_shot_uses_its_project_names(tmp_path):
    shot = shot_in(tmp_path, "bodies: {riser: {zone: cyl2, axis: z}}\n")
    scene = Scene.make(shot, TwoBodies(), VIEWS)
    assert isinstance(scene.source, DeclaredSource)
    assert z_of(scene.data(0).body("riser")) == 0.7


def test_follow_true_and_follow_by_name(tmp_path):
    zs = TwoBodies().body(0, "cyl2").points[:, 2]
    station = float(zs[abs(zs - 0.7).argmin()])            # on a ring of the sphere's points
    camera = {"view": "side", "follow": True, "station": station}
    scene = Scene.make(shot_in(tmp_path, "bodies: {riser: {zone: cyl2}}\n", camera),
                       TwoBodies(), VIEWS)
    assert scene.camera.view(0, scene.data(0)).focal == pytest.approx((0, 0, station), abs=1e-6)
    named = ShotCamera({"view": "side", "follow": "riser", "station": station}, VIEWS, {}, Checker())
    assert named.view(0, scene.data(0)).focal == pytest.approx((0, 0, station), abs=1e-6)
    with pytest.raises(LookupError, match="name the body"):
        plain = Scene.make(shot_in(tmp_path / "..", None, camera, body="cyl"), TwoBodies(), VIEWS)
        plain.camera.view(0, plain.data(0))


def test_the_declaration_is_in_the_frame_key(tmp_path):
    a = frame_key(Scene.make(shot_in(tmp_path, "bodies: {riser: {zone: cyl}}\n"), TwoBodies(), VIEWS), 0)
    b = frame_key(Scene.make(shot_in(tmp_path, "bodies: {riser: {zone: cyl2}}\n"), TwoBodies(), VIEWS), 0)
    c = frame_key(Scene.make(shot_in(tmp_path, "bodies: {riser: {zone: cyl}}\n"), TwoBodies(), VIEWS), 0)
    assert a != b and a == c
