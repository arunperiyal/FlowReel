"""Derived fields against flows with known answers (docs/PLAN.md, Section 16).

All grids are generated here. The VTK point gradient is exact for a linear velocity
(solid-body rotation, plane shear), so those tests use round-off tolerances everywhere,
boundary nodes included. For a curved profile (Burgers vortex, the annulus) it is
second-order at interior nodes of a regular hexahedral grid and one-sided, first-order,
at boundary nodes; the tolerances follow the mesh spacing and say which nodes they cover.
"""
import numpy as np
import pytest
import pyvista as pv

from flowreel import fields
from flowreel.fields import registry


def box_grid(dimensions, lo, hi, tets=False):
    """A regular box of hexahedra (or of tetrahedra) as an unstructured grid."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    spacing = (hi - lo) / (np.asarray(dimensions) - 1)
    grid = pv.ImageData(dimensions=dimensions, spacing=spacing, origin=lo)
    grid = grid.cast_to_unstructured_grid()
    # Double-precision coordinates, with the faces exactly at lo and hi.
    index = np.rint((np.asarray(grid.points, float) - lo) / spacing)
    grid.points = lo + (hi - lo) * index / (np.asarray(dimensions) - 1)
    return grid.triangulate() if tets else grid


def boundary_faces(grid, select):
    """The boundary faces of ``grid`` whose corner points all satisfy ``select(points)``."""
    surface = grid.extract_surface(algorithm="dataset_surface")
    keep = [i for i in range(surface.n_cells)
            if select(surface.points[surface.get_cell(i).point_ids]).all()]
    return surface.extract_cells(keep).extract_surface(algorithm="dataset_surface").clean()


def reverse_some_windings(wall, every=3):
    """The same surface with the winding of every ``every``-th cell reversed."""
    faces = [list(wall.get_cell(i).point_ids) for i in range(wall.n_cells)]
    for face in faces[::every]:
        face.reverse()
    return pv.PolyData.from_irregular_faces(wall.points, faces)


# ---------------------------------------------------------------- solid-body rotation

OMEGA = np.array([0.3, -0.5, 1.1])  # rotation vector, deliberately off the axes


@pytest.fixture(params=["hexahedra", "tetrahedra"])
def rotating(request):
    grid = box_grid((7, 6, 5), (-1, -1, 0), (1, 1.5, 1), tets=request.param == "tetrahedra")
    velocity = np.cross(OMEGA, grid.points)
    grid["U"], grid["V"], grid["W"] = velocity.T
    return grid


def test_solid_body_rotation(rotating):
    """vorticity = 2 omega, Q = |omega|^2, lambda2 = -|omega|^2, at every node."""
    out = fields.compute(rotating, ["vorticity", "vorticity_x", "vorticity_y", "vorticity_z",
                                    "Q", "lambda2", "velocity_gradient"])
    w2 = OMEGA @ OMEGA
    tol = 1e-10
    assert np.abs(out["vorticity"] - 2 * OMEGA).max() < tol
    for k, axis in enumerate("xyz"):
        assert np.array_equal(out[f"vorticity_{axis}"], out["vorticity"][:, k])
    assert np.abs(out["Q"] - w2).max() < tol
    assert np.abs(out["lambda2"] + w2).max() < tol
    # G[i, j] = d u_i / d x_j: for u = omega x r, dU/dy = -omega_z and dV/dx = +omega_z.
    assert np.abs(out["velocity_gradient"][:, 0, 1] + OMEGA[2]).max() < tol
    assert np.abs(out["velocity_gradient"][:, 1, 0] - OMEGA[2]).max() < tol


def test_gradient_computed_once(rotating):
    """Five fields that need the gradient cost one gradient computation."""
    record = registry.describe("velocity_gradient")
    calls = []

    def counting(grid, velocity):
        calls.append(1)
        return record.func(grid, velocity)

    registry.register("velocity_gradient", record.needs, replace=True)(counting)
    try:
        fields.compute(rotating, ["lambda2", "vorticity_x", "Q", "vorticity", "vorticity_z"])
    finally:
        registry.register("velocity_gradient", record.needs, replace=True)(record.func)
    assert len(calls) == 1


def test_stored_derived_fields_are_ignored(rotating):
    """A stored (wrong) vorticity on the grid does not reach the result."""
    rotating["vorticity"] = np.full((rotating.n_points, 3), 99.0)
    rotating["Q"] = np.full(rotating.n_points, 99.0)
    out = fields.compute(rotating, ["vorticity", "Q"])
    assert np.abs(out["vorticity"] - 2 * OMEGA).max() < 1e-10
    assert np.abs(out["Q"] - OMEGA @ OMEGA).max() < 1e-10


# ---------------------------------------------------------------- plane shear on a wall

MU, RHO, U_INF = 0.02, 1.2, 3.0


def shear_flow(rate, curvature=0.0, tets=False, ny=11):
    """U = rate * y + curvature * y^2 over 0 <= y <= 1, with uniform pressure 5."""
    grid = box_grid((9, ny, 7), (0, 0, 0), (2, 1, 3), tets=tets)
    y = grid.points[:, 1]
    grid["U"] = rate * y + curvature * y**2
    grid["V"] = np.zeros(grid.n_points)
    grid["W"] = np.zeros(grid.n_points)
    grid["p"] = np.full(grid.n_points, 5.0)
    return grid


def lower_wall(grid):
    return boundary_faces(grid, lambda p: p[:, 1] < 1e-9)


def upper_wall(grid):
    return boundary_faces(grid, lambda p: p[:, 1] > 1 - 1e-9)


@pytest.mark.parametrize("tets", [False, True])
@pytest.mark.parametrize("rate", [4.0, -4.0])
def test_plane_shear_wall_shear_and_sign(rate, tets):
    """Wall at y = 0, fluid above: wall shear = mu dU/dy along +x, reversed with the flow."""
    grid = shear_flow(rate, tets=tets)
    wall = reverse_some_windings(lower_wall(grid))  # the winding must not matter
    out = fields.compute(grid, ["wall_shear", "skin_friction", "wall_normal", "wall_area"],
                         wall=wall, mu=MU, rho=RHO, u_inf=U_INF)
    assert out["wall_shear"].shape == (wall.n_cells, 3)
    assert np.abs(out["wall_normal"] - [0, 1, 0]).max() < 1e-12  # into the fluid
    assert np.abs(out["wall_shear"] - [MU * rate, 0, 0]).max() < 1e-12
    assert np.sign(out["wall_shear"][:, 0]).tolist() == [np.sign(rate)] * wall.n_cells
    q = 0.5 * RHO * U_INF**2
    assert np.abs(out["skin_friction"] - [MU * rate / q, 0, 0]).max() < 1e-12
    assert out["wall_area"].sum() == pytest.approx(2 * 3)


def test_plane_shear_upper_wall_has_opposite_sign():
    """Wall at y = 1, fluid below (n = -y): the slower fluid drags it back, -mu dU/dy."""
    grid = shear_flow(4.0)
    out = fields.compute(grid, ["wall_shear", "wall_normal"], wall=upper_wall(grid), mu=MU)
    assert np.abs(out["wall_normal"] - [0, -1, 0]).max() < 1e-12
    assert np.abs(out["wall_shear"] - [-MU * 4.0, 0, 0]).max() < 1e-12


def test_wall_normal_modes():
    """``keep`` uses the surface's winding, ``flip`` reverses it, ``auto`` finds the fluid."""
    grid = shear_flow(4.0)
    wall = lower_wall(grid)
    keep = fields.compute(grid, "wall_normal", wall=wall, wall_normals="keep")["wall_normal"]
    flip = fields.compute(grid, "wall_normal", wall=wall, wall_normals="flip")["wall_normal"]
    assert np.allclose(np.abs(keep[:, 1]), 1) and np.allclose(flip, -keep)
    with pytest.raises(ValueError, match="wall_normals"):
        fields.compute(grid, "wall_normal", wall=wall, wall_normals="outward")
    with pytest.raises(TypeError, match="PolyData"):
        fields.compute(grid, "wall_normal", wall=grid)


def test_wall_off_the_flow_nodes_warns():
    grid = shear_flow(4.0)
    wall = lower_wall(grid).translate((0.01, 0, 0.01))
    with pytest.warns(RuntimeWarning, match="nearest flow node"):
        fields.compute(grid, "wall_shear", wall=wall, mu=MU)


def test_curved_profile_wall_shear_is_first_order():
    """U = a y + b y^2: the one-sided gradient at the wall is off by b * h, no more.

    The wall nodes are boundary nodes of the flow grid, so the gradient there comes from
    the elements on the fluid side only: the error is b * h (h the first spacing) and
    halves with h.
    """
    rate, curvature = 4.0, -3.0
    errors = []
    for ny in (11, 21):
        grid = shear_flow(rate, curvature, ny=ny)
        shear = fields.compute(grid, "wall_shear", wall=lower_wall(grid), mu=MU)["wall_shear"]
        h = 1 / (ny - 1)
        error = np.abs(shear[:, 0] - MU * rate).max()
        assert error <= MU * abs(curvature) * h * (1 + 1e-9)
        assert np.sign(shear[:, 0]).min() == 1
        errors.append(error)
    assert errors[0] / errors[1] == pytest.approx(2.0, rel=1e-6)


def test_sectional_force_on_a_flat_wall():
    """Each strip carries (mu dU/dy, -(p - p_inf), 0) times its area."""
    grid = shear_flow(4.0)
    out = fields.compute(grid, ["sectional_force", "wall_traction"], wall=lower_wall(grid),
                         mu=MU, axis="z", sections=3, p_inf=1.0)
    strips = out["sectional_force"]
    assert np.abs(out["wall_traction"] - [MU * 4.0, -4.0, 0]).max() < 1e-12
    assert strips.axis == 2 and strips.width == pytest.approx(1.0)
    assert np.allclose(strips.position, [0.5, 1.5, 2.5])
    assert np.allclose(strips.force, np.tile([MU * 4.0 * 2, -4.0 * 2, 0], (3, 1)))
    assert np.allclose(strips.per_length, strips.force)
    assert np.allclose(strips.total, [MU * 4.0 * 6, -4.0 * 6, 0])
    part = fields.compute(grid, "sectional_force", wall=lower_wall(grid), mu=MU, axis=2,
                          sections=2, span=(0, 1))["sectional_force"]
    assert np.allclose(part.force, np.tile([MU * 4.0, -5.0, 0], (2, 1)))
    with pytest.raises(ValueError, match="axis"):
        fields.compute(grid, "sectional_force", wall=lower_wall(grid), mu=MU, axis="w")


# ---------------------------------------------------------------- cylinder in an annulus

RADIUS, CIRCULATION_A, PRESSURE_SLOPE = 0.5, 0.7, 3.0


@pytest.fixture(scope="module")
def annulus():
    """Potential vortex u_theta = A / r and p = k x around a cylinder of radius 0.5.

    96 cells around, 40 across (clustered at the cylinder), 8 along the span of 2.
    """
    r = RADIUS + 1.5 * np.linspace(0, 1, 41) ** 2
    theta = np.linspace(0, 2 * np.pi, 97)
    z = np.linspace(0, 2, 9)
    rr, tt, zz = np.meshgrid(r, theta, z, indexing="ij")
    grid = pv.StructuredGrid(rr * np.cos(tt), rr * np.sin(tt), zz)
    grid = grid.cast_to_unstructured_grid().clean(tolerance=1e-12)  # close the seam
    x, y = grid.points[:, 0], grid.points[:, 1]
    r2 = x**2 + y**2
    grid["velocity"] = np.column_stack([-CIRCULATION_A * y / r2, CIRCULATION_A * x / r2,
                                        np.zeros(grid.n_points)])
    grid["p"] = PRESSURE_SLOPE * x
    wall = boundary_faces(grid, lambda p: np.hypot(p[:, 0], p[:, 1]) < RADIUS + 1e-9)
    return grid, reverse_some_windings(wall)


def test_cylinder_wall_shear(annulus):
    """Curved wall: n is radial (out of the body), shear = -2 mu A / R^2 along theta.

    The first cell is 1.5/1600 thick; the one-sided gradient is within 0.5% (0.31% here).
    """
    grid, wall = annulus
    out = fields.compute(grid, ["wall_shear", "wall_normal", "wall_frame"], wall=wall, mu=MU)
    centre = out["wall_frame"].centre
    radial = centre * [1, 1, 0]
    radial /= np.linalg.norm(radial, axis=1)[:, None]
    tangent = np.column_stack([-radial[:, 1], radial[:, 0], np.zeros(len(radial))])
    assert wall.n_cells == 96 * 8
    assert np.einsum("ci,ci->c", out["wall_normal"], radial).min() > 1 - 1e-6
    exact = -2 * MU * CIRCULATION_A / RADIUS**2
    along = np.einsum("ci,ci->c", out["wall_shear"], tangent)
    assert np.abs(along / exact - 1).max() < 5e-3
    assert np.abs(np.einsum("ci,ci->c", out["wall_shear"], out["wall_normal"])).max() < 1e-12
    assert np.abs(out["wall_shear"][:, 2]).max() < 1e-12


def test_cylinder_sectional_force(annulus):
    """p = k x on a closed section: force = -k * (section area) * width along x.

    The shear of the potential vortex is a pure torque and adds no net force. The
    96-sided polygon has 0.07% less area than the circle; tolerance 0.2%.
    """
    grid, wall = annulus
    strips = fields.compute(grid, "sectional_force", wall=wall, mu=MU, axis="z",
                            sections=4)["sectional_force"]
    exact = -PRESSURE_SLOPE * np.pi * RADIUS**2 * 0.5
    assert strips.width == pytest.approx(0.5)
    assert np.abs(strips.force[:, 0] / exact - 1).max() < 2e-3
    assert np.abs(strips.force[:, 1:]).max() < 1e-9 * abs(exact)


# ---------------------------------------------------------------- Burgers vortex

GAMMA, CORE, STRAIN = 2.0, 0.5, 0.4  # circulation, core radius, axial strain rate


def burgers(n, tets=False):
    """Burgers vortex along z on [-2, 2]^2 x [-0.5, 0.5] with n x n x 9 nodes.

    u_r = -a r / 2, u_z = a z, u_theta = Gamma / (2 pi r) (1 - exp(-r^2 / rc^2)).
    Returns the grid, the exact vorticity_z and the exact Q.
    """
    grid = box_grid((n, n, 9), (-2, -2, -0.5), (2, 2, 0.5), tets=tets)
    x, y, z = grid.points.T
    s = (x**2 + y**2) / CORE**2
    safe = np.where(s > 0, s, 1.0)
    swirl = GAMMA / (2 * np.pi * CORE**2) * np.where(s > 0, -np.expm1(-s) / safe, 1.0)
    grid["velocity"] = np.column_stack([-STRAIN * x / 2 - y * swirl,
                                        -STRAIN * y / 2 + x * swirl, STRAIN * z])
    vorticity_z = GAMMA / (np.pi * CORE**2) * np.exp(-s)
    q = vorticity_z**2 / 4 - (vorticity_z / 2 - swirl) ** 2 - 0.75 * STRAIN**2
    return grid, vorticity_z, q


def interior_nodes(grid):
    x, y, z = np.abs(grid.points).T
    return (x < 2 - 1e-9) & (y < 2 - 1e-9) & (z < 0.5 - 1e-9)


def test_burgers_vortex_profile_hexahedra():
    """Vorticity profile and Q on hexahedra, spacing h = rc / 8.

    Interior nodes: second-order; the error is 0.78% of the peak vorticity and 1.7% of
    the peak Q (tolerances 1% and 2.5%), and falls four times when h is halved. Boundary
    nodes get the same tolerance here only because this flow is linear in z and smooth at
    the side faces; they are checked separately to say so.
    """
    errors = {}
    for n in (33, 65):
        grid, exact_w, exact_q = burgers(n)
        out = fields.compute(grid, ["vorticity", "Q", "lambda2"])
        inner = interior_nodes(grid)
        errors[n] = np.abs(out["vorticity"][inner, 2] - exact_w[inner]).max() / exact_w.max()
        assert np.abs(out["vorticity"][:, :2]).max() < 1e-12
    assert np.abs(out["vorticity"][inner, 2] - exact_w[inner]).max() < 0.01 * exact_w.max()
    assert np.abs(out["vorticity"][~inner, 2] - exact_w[~inner]).max() < 0.01 * exact_w.max()
    assert np.abs(out["Q"][inner] - exact_q[inner]).max() < 0.025 * exact_q.max()
    assert np.abs(out["Q"][~inner] - exact_q[~inner]).max() < 0.025 * exact_q.max()
    assert errors[33] / errors[65] == pytest.approx(4.0, rel=0.1)  # second order


def test_burgers_vortex_core():
    """Q is positive and lambda2 negative in the core; Q is negative far from it."""
    grid, exact_w, exact_q = burgers(65)
    out = fields.compute(grid, ["Q", "lambda2", "vorticity_z"])
    r = np.hypot(grid.points[:, 0], grid.points[:, 1])
    core = r < 0.5 * CORE
    assert exact_q[core].min() > 0 and out["Q"][core].min() > 0
    assert out["lambda2"][core].max() < 0
    assert out["vorticity_z"][core].min() > 0  # anticlockwise seen from +z, Gamma > 0
    far = r > 3 * CORE
    assert out["Q"][far].max() < 0  # outside the core strain wins: axial plus the swirl's
    assert np.abs(out["Q"][far] - exact_q[far]).max() < 0.002 * exact_q.max()


def test_burgers_vortex_tetrahedra_boundary_is_one_sided():
    """On tetrahedra the boundary nodes are clearly worse than the interior.

    Interior: 1.0% of the peak vorticity (tolerance 1.5%). Boundary nodes, where only the
    elements on the inner side contribute: 2.9% (tolerance 4%).
    """
    grid, exact_w, _ = burgers(65, tets=True)
    w = fields.compute(grid, "vorticity_z")["vorticity_z"]
    inner = interior_nodes(grid)
    inside = np.abs(w[inner] - exact_w[inner]).max() / exact_w.max()
    edge = np.abs(w[~inner] - exact_w[~inner]).max() / exact_w.max()
    assert inside < 0.015
    assert edge < 0.04
    assert edge > inside
