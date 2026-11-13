"""speed, velocity_relative and pressure_coefficient with exact values."""
import numpy as np
import pytest

from flowreel import fields


@pytest.fixture
def grid(toy_source):
    return toy_source.flow(0, ["U", "V", "W", "p"], None)


def test_speed(grid):
    r = np.hypot(grid.points[:, 0], grid.points[:, 1])
    assert np.allclose(fields.compute(grid, "speed")["speed"], r)  # omega = 1


def test_velocity_relative(grid):
    out = fields.compute(grid, ["velocity", "velocity_relative"], body_velocity=(0.5, 0, -1))
    assert np.allclose(out["velocity_relative"], out["velocity"] - [0.5, 0, -1])
    per_point = np.tile([0.0, 2.0, 0.0], (grid.n_points, 1))
    rel = fields.compute(grid, "velocity_relative", body_velocity=per_point)["velocity_relative"]
    assert np.allclose(rel[:, 1], grid["V"] - 2)
    with pytest.raises(ValueError, match="shape"):
        fields.compute(grid, "velocity_relative", body_velocity=(1, 2))
    with pytest.raises(TypeError, match="body_velocity"):
        fields.compute(grid, "velocity_relative")


def test_pressure_coefficient(grid):
    cp = fields.compute(grid, "pressure_coefficient", rho=2.0, u_inf=3.0, p_inf=0.25)
    assert np.allclose(cp["pressure_coefficient"], (grid["p"] - 0.25) / 9.0)
    default = fields.compute(grid, "pressure_coefficient", rho=2.0, u_inf=1.0)
    assert np.allclose(default["pressure_coefficient"], grid["p"])
    with pytest.raises(TypeError, match="rho"):
        fields.compute(grid, "pressure_coefficient", u_inf=1.0)
    with pytest.raises(ValueError, match="positive"):
        fields.compute(grid, "pressure_coefficient", rho=1.0, u_inf=0.0)
