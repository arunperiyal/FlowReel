"""The shapes of virtual bodies: pendulum, spring, mass, with exact positions."""
import numpy as np
import pytest

from flowreel.sources.bodies import get_body


def extent(surface):
    p = np.asarray(surface.points)
    return p.min(axis=0), p.max(axis=0)


def test_pendulum_hangs_and_swings():
    pend = get_body("pendulum")
    lo, hi = extent(pend(length=2.0, bob=0.3))
    assert np.isclose(lo[1], -2.3, atol=1e-3) and np.isclose(hi[0], 0.3, atol=1e-3)
    lo, hi = extent(pend(length=2.0, bob=0.3, angle=np.pi / 2))   # about +z: down turns to +x
    assert np.isclose(hi[0], 2.3, atol=1e-3) and np.isclose(lo[1], -0.3, atol=1e-3)
    lo, _ = extent(pend(length=1.0, bob=0.1, angle=np.pi / 2, swing=(1, 0, 0)))   # about +x: to -z
    assert np.isclose(lo[2], -1.1, atol=1e-3)


def test_spring_stretches_along_its_direction():
    lo, hi = extent(get_body("spring")(length=3.0, radius=0.2, wire=0.02))
    assert np.isclose(lo[1], -3.0, atol=0.03) and np.isclose(hi[1], 0.0, atol=0.03)
    assert np.isclose(hi[0], 0.22, atol=0.01)
    lo, hi = extent(get_body("spring")(length=1.0, direction=(1, 0, 0)))
    assert np.isclose(hi[0], 1.0, atol=0.03)


def test_mass_moves_with_its_offsets():
    lo, hi = extent(get_body("mass")(size=0.4, y=-1.0))
    assert np.allclose(lo, [-0.2, -1.2, -0.2]) and np.allclose(hi, [0.2, -0.8, 0.2])


def test_zero_direction():
    with pytest.raises(ValueError, match="zero vector"):
        get_body("spring")(direction=(0, 0, 0))
