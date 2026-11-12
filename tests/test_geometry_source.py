"""The geometry adapter, the body registry and the grooved cylinder."""
import tomllib
from importlib import import_module
from pathlib import Path

import numpy as np
import pytest
import pyvista as pv

from flowreel.sources import Source, bodies
from flowreel.sources.bodies import groove_angle, grooved_cylinder
from flowreel.sources.geometry import GeometrySource

SMALL = {"samples": (49, 361)}  # one point per degree keeps the tests fast


def radii(mesh):
    return np.hypot(mesh.points[:, 1], mesh.points[:, 2])


def test_body_registry():
    @bodies.register_body("test-ball")
    def ball(radius=1.0):
        return pv.Sphere(radius=radius)

    assert "test-ball" in bodies.available_bodies()
    assert bodies.get_body("test-ball") is ball
    with pytest.raises(ValueError, match="already"):
        bodies.register_body("test-ball", ball)
    with pytest.raises(KeyError, match="available"):
        bodies.get_body("nope")
    assert "grooved_cylinder" in bodies.available_bodies()


def test_source_has_a_body_and_no_flow():
    src = GeometrySource("grooved_cylinder", params=SMALL, frames=5, dt=0.25)
    assert isinstance(src, Source)
    assert src.steps() == [0, 1, 2, 3, 4]
    assert src.time(4) == 1.0
    assert src.fields() == []
    assert isinstance(src.body(0), pv.PolyData)
    assert np.allclose(src.bounds().lo, (0, -0.5, -0.5), atol=1e-3)
    assert np.allclose(src.bounds().hi, (12, 0.5, 0.5), atol=1e-3)
    assert 0 < src.memory_per_step(None) < 1e-2
    with pytest.raises(LookupError, match="no flow data"):
        src.flow(0, ["U"], None)
    with pytest.raises(KeyError):
        src.series("lift")
    with pytest.raises(KeyError, match="no step 5"):
        src.body(5)


def test_source_defaults_to_one_step_and_checks_parameters():
    assert GeometrySource("grooved_cylinder", params=SMALL).steps() == [0]
    with pytest.raises(TypeError, match="it takes"):
        GeometrySource("grooved_cylinder", params={"groove_count": 3})
    with pytest.raises(KeyError, match="unknown body"):
        GeometrySource("nope")
    with pytest.raises(ValueError):
        GeometrySource("grooved_cylinder", frames=0)


def test_build_overrides_parameters_without_changing_the_source():
    src = GeometrySource("grooved_cylinder", params={**SMALL, "caps": False})
    assert np.allclose(radii(src.build(cut_front=-1.0)), 0.5)   # nothing cut yet
    assert radii(src.body(0)).min() < 0.45     # the source itself is still fully carved
    assert src.params == {**SMALL, "caps": False}


def test_grooved_cylinder_is_pure():
    a, b = grooved_cylinder(**SMALL, cut_front=4.0), grooved_cylinder(**SMALL, cut_front=4.0)
    assert np.array_equal(a.points, b.points)
    assert np.array_equal(a["fresh"], b["fresh"])


def test_grooved_cylinder_shape():
    mesh = grooved_cylinder(**SMALL, caps=False)
    r = radii(mesh)
    assert r.max() == pytest.approx(0.5)
    assert r.min() == pytest.approx(0.5 - 0.08)
    assert mesh.bounds[0] == 0 and mesh.bounds[1] == 12
    assert set(mesh.point_data.keys()) == {"groove", "fresh"}
    assert np.allclose(mesh["groove"], (0.5 - r) / 0.08, atol=1e-5)
    assert not mesh["fresh"].any()


def groove_centres(mesh, x):
    """Angles (degrees, atan2(y, z)) of the groove floors on the ring at ``x``."""
    ring = np.isclose(mesh.points[:, 0], x) & (mesh["groove"] > 0.999)
    angle = np.sort(np.degrees(np.arctan2(mesh.points[ring, 1], mesh.points[ring, 2])) % 360)
    groups = np.split(angle, np.flatnonzero(np.diff(angle) > 5) + 1)
    return [float(np.mean(g)) for g in groups]


def test_groove_count_phase_and_turns():
    mesh = grooved_cylinder(**SMALL, caps=False)
    assert np.allclose(groove_centres(mesh, 0.0), [45, 135, 225, 315], atol=1.0)
    # One turn over the span: an eighth of the span on, the grooves are 45 degrees round.
    assert np.allclose(groove_centres(mesh, 1.5)[1:4], [90, 180, 270], atol=1.0)
    three = grooved_cylinder(**SMALL, caps=False, grooves=3, phase=10.0, turns=0.0)
    for x in (0.0, 6.0):
        assert np.allclose(groove_centres(three, x), [10, 130, 250], atol=1.0)
    back = grooved_cylinder(**SMALL, caps=False, turns=-1.0, phase=100.0, grooves=2)
    assert np.allclose(groove_centres(back, 1.5), [55, 235], atol=1.0)
    assert np.degrees(groove_angle(6.0, 1, turns=1.0)) == pytest.approx(45 + 90 + 180)


def test_groove_width_and_depth():
    mesh = grooved_cylinder(**SMALL, caps=False, width=0.3, depth=0.1, radius=0.6, turns=0.0)
    ring = np.isclose(mesh.points[:, 0], 0.0)
    cut = np.count_nonzero(mesh["groove"][ring] > 0.5) / np.count_nonzero(ring)
    expected = 4 * 2 * np.arcsin(0.3 / 1.2) / (2 * np.pi)   # four grooves of that chord
    assert cut == pytest.approx(expected, abs=0.02)
    assert radii(mesh).min() == pytest.approx(0.5)
    with pytest.raises(ValueError):
        grooved_cylinder(depth=0.6)
    with pytest.raises(ValueError):
        grooved_cylinder(width=1.0)


def test_cut_front_carves_along_the_span():
    mesh = grooved_cylinder(**SMALL, caps=False, cut_front=6.0)
    x, r = mesh.points[:, 0], radii(mesh)
    assert np.allclose(r[x > 6.0], 0.5)                       # ahead of the front: smooth
    assert r[x < 5.5].min() == pytest.approx(0.42)            # well behind: full depth
    assert mesh["fresh"].max() > 0.5
    assert not mesh["fresh"][x < 6.0 - 0.8].any()             # the glow has faded
    assert not mesh["fresh"][x > 6.0].any()
    done = grooved_cylinder(**SMALL, caps=False, cut_front=14.0)
    assert np.allclose(done.points, grooved_cylinder(**SMALL, caps=False).points)


def test_caps_close_the_ends():
    capped = grooved_cylinder(**SMALL)
    bare = grooved_cylinder(**SMALL, caps=False)
    assert isinstance(capped, pv.PolyData)
    assert set(capped.point_data.keys()) == {"groove", "fresh"}
    assert capped.area > bare.area + 2 * 0.9 * np.pi * 0.42**2
    assert capped.area < bare.area + 2 * np.pi * 0.5**2


def test_no_grooves_is_a_smooth_cylinder():
    assert np.allclose(radii(grooved_cylinder(**SMALL, caps=False, grooves=0)), 0.5)


def test_entry_points_name_the_adapters():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    targets = project["project"]["entry-points"]["flowreel.sources"]
    assert set(targets) >= {"vtk", "geometry"}
    for target in (targets["vtk"], targets["geometry"]):
        module, attribute = target.split(":")
        assert callable(getattr(import_module(module), attribute))


def test_body_is_named_after_the_registered_body():
    from flowreel.sources.geometry import GeometrySource
    src = GeometrySource("grooved_cylinder", params={"samples": (21, 41)})
    assert src.bodies() == ["grooved_cylinder"]
    assert src.body(0, "grooved_cylinder").n_points == src.body(0).n_points
    with pytest.raises(KeyError):
        src.body(0, "sphere")
