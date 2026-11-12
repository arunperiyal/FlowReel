"""Wall fields on a closed body with no axis: Stokes flow past a sphere.

For a sphere of radius ``a`` in a stream ``U`` along z, creeping flow has the exact
solution (Batchelor, section 4.9)

    u_r     =  U cos(t) (1 - 3a/(2r) + a^3/(2r^3))
    u_theta = -U sin(t) (1 - 3a/(4r) - a^3/(4r^3))
    p       =  p_inf - 3 mu U a cos(t) / (2 r^2)

and the traction on the sphere is the same everywhere, ``3 mu U / (2a)`` along z, so the
drag is ``6 pi mu a U``: one third from pressure and two thirds from shear. The wall shear
is the tangential part, ``3 mu U / (2a) (z - (z.n) n)``.

The mesh is a shell of wedges grown radially from an icosphere, so the wall is made of
triangles and has no poles, no axis and no spanwise direction.

Tolerances are for this mesh (33 306 nodes): measured errors are 2.1% of the traction for
the shear, 1.5% for the drag and 2.2% for the shear part of the drag. They fall as the
mesh is refined (0.3%, 0.2% and 0.3% with 48 layers on a finer icosphere).
"""
import numpy as np
import pytest
import pyvista as pv

from flowreel import fields

A, U, MU, P_INF = 0.5, 2.0, 0.3, 7.0
T0 = 3 * MU * U / (2 * A)                 # magnitude of the uniform traction


def stokes(points):
    r = np.linalg.norm(points, axis=1)
    n = points / r[:, None]
    cos = n[:, 2]
    ez = np.array([0.0, 0.0, 1.0])
    theta_sin = cos[:, None] * n - ez      # theta-hat times sin(theta)
    u_r = U * cos * (1 - 1.5 * A / r + 0.5 * A**3 / r**3)
    u_t = -U * (1 - 0.75 * A / r - 0.25 * A**3 / r**3)
    velocity = u_r[:, None] * n + u_t[:, None] * theta_sin
    return velocity, P_INF - 1.5 * MU * U * A * cos / r**2


def shell(subdivisions, layers, thickness):
    """Wedges between ``layers + 1`` spheres from r = A to A + thickness, and the wall."""
    ico = pv.Icosphere(radius=1.0, nsub=subdivisions)
    unit = np.asarray(ico.points, dtype=float)
    unit /= np.linalg.norm(unit, axis=1)[:, None]
    tris = ico.faces.reshape(-1, 4)[:, 1:]
    n = len(unit)
    radii = A + thickness * np.linspace(0, 1, layers + 1) ** 1.5      # finer at the wall
    points = np.concatenate([unit * r for r in radii])
    cells = np.concatenate([np.hstack([tris + k * n, tris + (k + 1) * n]) for k in range(layers)])
    grid = pv.UnstructuredGrid({pv.CellType.WEDGE: cells}, points)
    grid.point_data["velocity"], grid.point_data["p"] = stokes(points)
    faces = np.hstack([np.full((len(tris), 1), 3), tris]).ravel()
    return grid, pv.PolyData(unit * A, faces)


@pytest.fixture(scope="module")
def sphere():
    return shell(subdivisions=4, layers=12, thickness=0.25)


def test_sphere_wall_shear_and_normals(sphere):
    grid, wall = sphere
    out = fields.compute(grid, ["wall_shear", "wall_normal", "wall_frame"], wall=wall, mu=MU)
    n = out["wall_frame"].centre / np.linalg.norm(out["wall_frame"].centre, axis=1)[:, None]
    assert np.allclose(out["wall_normal"], n, atol=5e-3)              # out of the body
    exact = T0 * (np.array([0, 0, 1.0]) - n[:, 2:3] * n)
    assert np.abs(out["wall_shear"] - exact).max() < 0.03 * T0


def test_sphere_traction_is_uniform(sphere):
    grid, wall = sphere
    t = fields.compute(grid, "wall_traction", wall=wall, mu=MU, p_inf=P_INF)["wall_traction"]
    assert np.abs(t - [0, 0, T0]).max() < 0.03 * T0


def test_sphere_drag_and_moment(sphere):
    grid, wall = sphere
    load = fields.compute(grid, "wall_force", wall=wall, mu=MU)["wall_force"]
    drag = 6 * np.pi * MU * A * U
    assert load.force[2] == pytest.approx(drag, rel=0.02)
    assert np.abs(load.force[:2]).max() < 1e-3 * drag
    assert np.abs(load.moment).max() < 1e-3 * drag * A               # no torque about the centre
    # about another point the moment is r x F for a load through the centre
    moved = fields.compute(grid, "wall_force", wall=wall, mu=MU, about=(1.0, 0, 0))["wall_force"]
    assert moved.moment == pytest.approx(np.cross([-1.0, 0, 0], load.force), abs=1e-3 * drag)


def test_drag_splits_one_third_pressure_two_thirds_shear(sphere):
    grid, wall = sphere
    out = fields.compute(grid, ["wall_shear", "wall_frame"], wall=wall, mu=MU)
    shear_drag = (out["wall_shear"][:, 2] * out["wall_frame"].area).sum()
    assert shear_drag == pytest.approx(4 * np.pi * MU * A * U, rel=0.03)
