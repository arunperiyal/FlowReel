"""Wall fields: shear stress and skin friction on the body surface.

Follows ``prototype/afms/surface_data.py``. Everything comes from the velocity gradient
(and pressure) of the flow grid, sampled at the flow node nearest to each wall node; the
solver's stored vorticity or wall shear is never used (docs/PLAN.md, Section 6).

Conventions
-----------
- The wall is a ``pyvista.PolyData`` passed as the parameter ``wall`` (for example
  ``source.body(step)``). Wall fields have one row per **cell** of that surface.
- The normal ``n`` is the unit normal pointing **from the wall into the fluid** (out of
  the body).
- Stresses are those the **fluid exerts on the wall**. The traction on the wall is
  ``t = -p n + tau_w`` with the wall shear ``tau_w`` the tangential part of
  ``mu (grad u + grad u^T) n``. ``tau_w`` points the way the fluid next to the wall
  moves relative to it; it reverses where the flow is separated.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pyvista as pv
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from vtk.util.numpy_support import vtk_to_numpy

from flowreel.fields.basic import dynamic_pressure
from flowreel.fields.registry import register

NORMAL_MODES = ("auto", "keep", "flip")


@dataclass(frozen=True)
class WallFrame:
    """Geometry of a wall surface and its link to the flow grid.

    ``normal``: ``(n_cells, 3)`` unit normals into the fluid. ``area``: ``(n_cells,)``.
    ``centre``: ``(n_cells, 3)`` cell centres. ``nodes``: ``(n_wall_points,)`` index of
    the flow node nearest to each wall node. ``gap``: largest distance between a wall
    node and its flow node (length unit). ``connectivity``, ``offsets``: the wall's cells
    as point ids and the start of each cell in them.
    """

    normal: np.ndarray
    area: np.ndarray
    centre: np.ndarray
    nodes: np.ndarray
    gap: float
    connectivity: np.ndarray
    offsets: np.ndarray

    def cell_mean(self, point_values) -> np.ndarray:
        """Mean over each wall cell's corners of values given per **wall** point."""
        values = np.asarray(point_values)[self.connectivity]
        count = np.diff(self.offsets)
        total = np.add.reduceat(values, self.offsets[:-1], axis=0)
        return total / count.reshape((-1,) + (1,) * (values.ndim - 1))

    def sample(self, flow_values) -> np.ndarray:
        """Values given per **flow** point, taken at the wall nodes and averaged per cell."""
        return self.cell_mean(np.asarray(flow_values)[self.nodes])


def _regions(connectivity, offsets, n_points) -> np.ndarray:
    """Connected-region label of every cell (cells sharing a point are connected)."""
    count = np.diff(offsets)
    first = np.repeat(connectivity[offsets[:-1]], count)
    graph = coo_matrix((np.ones(connectivity.size), (connectivity, first)),
                       shape=(n_points, n_points))
    _, labels = connected_components(graph, directed=False)
    return labels[connectivity[offsets[:-1]]]


@register("wall_frame")
def wall_frame(grid, *, wall, wall_normals="auto", wall_tolerance=None) -> WallFrame:
    """Normals, areas and flow-node matches of the wall surface (a :class:`WallFrame`).

    ``wall``: ``pyvista.PolyData`` of polygons, in the grid's coordinates.
    ``wall_normals``: how the normals are made to point into the fluid.
    ``"auto"`` (default) makes the winding consistent, then, for each connected part of
    the wall, turns the normals towards the nearest flow nodes that are off the wall;
    ``"keep"`` trusts the surface's own winding (right-hand rule), ``"flip"`` reverses it.
    Use ``keep`` or ``flip`` for a zero-thickness wall with fluid on both sides.
    ``wall_tolerance``: a ``RuntimeWarning`` is raised if a wall node lies farther than
    this from every flow node (default: 1e-6 of the wall's bounding-box diagonal), since
    the gradient is then sampled off the wall.
    """
    if not isinstance(wall, pv.PolyData):
        raise TypeError("wall must be a pyvista.PolyData (use extract_surface() first)")
    if wall_normals not in NORMAL_MODES:
        raise ValueError(f"wall_normals must be one of {NORMAL_MODES}, not {wall_normals!r}")
    polys = wall.GetPolys()
    if wall.n_cells == 0 or polys.GetNumberOfCells() != wall.n_cells:
        raise ValueError("wall must contain polygons only (use triangulate() for strips)")
    surface = wall.copy(deep=False)
    surface.clear_data()
    if wall_normals == "auto":
        # One winding per connected part; the cells keep their order.
        surface = surface.compute_normals(
            cell_normals=True, point_normals=False, consistent_normals=True,
            auto_orient_normals=False, split_vertices=False)
        polys = surface.GetPolys()
    else:
        surface = surface.compute_normals(
            cell_normals=True, point_normals=False, consistent_normals=False,
            auto_orient_normals=False, split_vertices=False)
    connectivity = vtk_to_numpy(polys.GetConnectivityArray()).astype(np.int64)
    offsets = vtk_to_numpy(polys.GetOffsetsArray()).astype(np.int64)
    normal = np.array(surface.cell_data["Normals"], dtype=float)
    area = np.array(surface.compute_cell_sizes(length=False, area=True, volume=False)
                    .cell_data["Area"], dtype=float)
    centre = np.add.reduceat(surface.points[connectivity], offsets[:-1], axis=0)
    centre = centre / np.diff(offsets)[:, None]

    flow_points = np.asarray(grid.points, dtype=float)
    distance, nodes = cKDTree(flow_points).query(surface.points)
    gap = float(distance.max())
    if wall_tolerance is None:
        wall_tolerance = 1e-6 * float(np.linalg.norm(np.ptp(surface.points, axis=0)))
    if gap > wall_tolerance:
        warnings.warn(f"wall nodes lie up to {gap:.3g} from the nearest flow node "
                      f"(tolerance {wall_tolerance:.3g}); wall fields are sampled off the wall",
                      RuntimeWarning, stacklevel=2)

    if wall_normals == "flip":
        normal = -normal
    elif wall_normals == "auto":
        off_wall = np.ones(len(flow_points), dtype=bool)
        off_wall[nodes[distance <= wall_tolerance]] = False
        if not off_wall.any():
            raise ValueError("no flow nodes off the wall: cannot orient the wall normals")
        fluid = flow_points[off_wall]
        _, nearest = cKDTree(fluid).query(centre)
        side = np.sign(np.einsum("ci,ci->c", fluid[nearest] - centre, normal))
        region = _regions(connectivity, offsets, surface.n_points)
        vote = np.bincount(region, weights=side)
        normal = normal * np.where(vote[region] < 0, -1.0, 1.0)[:, None]
    return WallFrame(normal=normal, area=area, centre=centre, nodes=nodes, gap=gap,
                     connectivity=connectivity, offsets=offsets)


@register("wall_normal", "wall_frame")
def wall_normal(grid, frame) -> np.ndarray:
    """Unit normal of each wall cell, pointing from the wall into the fluid, ``(n_cells, 3)``."""
    return frame.normal


@register("wall_area", "wall_frame")
def wall_area(grid, frame) -> np.ndarray:
    """Area of each wall cell, ``(n_cells,)``, in length unit squared."""
    return frame.area


@register("wall_pressure", ("pressure", "wall_frame"))
def wall_pressure(grid, pressure, frame) -> np.ndarray:
    """Pressure on each wall cell (mean of its nodes' values), ``(n_cells,)``."""
    return frame.sample(pressure)


@register("wall_shear", ("velocity_gradient", "wall_frame"))
def wall_shear(grid, gradient, frame, *, mu) -> np.ndarray:
    """Wall shear stress vector on each wall cell, ``(n_cells, 3)``.

    The tangential part of ``mu (grad u + grad u^T) n``, with ``n`` into the fluid: the
    viscous force per unit area the fluid exerts on the wall. Its component along the
    outer flow is positive for attached flow and negative under reversed flow.
    ``mu``: dynamic viscosity (``rho * nu``; the molecular one, eddy viscosity vanishes
    at the wall). The gradient is the one-sided point gradient at the wall nodes,
    averaged over each cell's corners, so it is first-order in the wall-normal spacing.
    """
    grad = frame.sample(gradient)
    stress = float(mu) * np.einsum("cij,cj->ci", grad + grad.transpose(0, 2, 1), frame.normal)
    along_normal = np.einsum("ci,ci->c", stress, frame.normal)
    return stress - along_normal[:, None] * frame.normal


@register("skin_friction", "wall_shear")
def skin_friction(grid, shear, *, rho, u_inf) -> np.ndarray:
    """Skin-friction coefficient vector ``wall_shear / q``, ``(n_cells, 3)``.

    ``q = rho * u_inf**2 / 2``. Same direction and sign convention as ``wall_shear``.
    """
    return shear / dynamic_pressure(rho, u_inf)
