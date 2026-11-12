"""Fields of the velocity gradient: the gradient itself, vorticity, Q and lambda2.

Convention used everywhere: ``G[n, i, j] = d u_i / d x_j`` at point ``n`` (row = velocity
component, column = direction of the derivative), in velocity unit over length unit.
"""
from __future__ import annotations

import numpy as np

from flowreel.fields.registry import register


@register("velocity_gradient", "velocity")
def velocity_gradient(grid, velocity) -> np.ndarray:
    """Point gradient of velocity, ``(n_points, 3, 3)`` with ``G[n, i, j] = d u_i / d x_j``.

    Computed by VTK (``compute_derivative``): at a node of an unstructured grid it is the
    mean of the gradients of the elements sharing the node. On a boundary node only the
    elements on the inner side exist, so the value there is one-sided and less accurate
    than in the interior.
    """
    work = grid.copy(deep=False)
    work.clear_data()
    work.point_data["_velocity"] = velocity
    grad = work.compute_derivative(scalars="_velocity", gradient="_gradient")
    return np.asarray(grad.point_data["_gradient"], dtype=float).reshape(-1, 3, 3)


@register("vorticity", "velocity_gradient")
def vorticity(grid, gradient) -> np.ndarray:
    """Vorticity, the curl of velocity, ``(n_points, 3)``; twice the local rotation rate.

    Right-handed: ``vorticity_z = dV/dx - dU/dy`` is positive for anticlockwise rotation
    seen from +z.
    """
    return np.column_stack([gradient[:, 2, 1] - gradient[:, 1, 2],
                            gradient[:, 0, 2] - gradient[:, 2, 0],
                            gradient[:, 1, 0] - gradient[:, 0, 1]])


def strain_and_rotation(gradient) -> tuple[np.ndarray, np.ndarray]:
    """Split a gradient ``(n, 3, 3)`` into the strain rate ``S`` and the rotation ``Omega``.

    ``S = (G + G^T) / 2`` (symmetric), ``Omega = (G - G^T) / 2`` (antisymmetric).
    """
    transpose = gradient.transpose(0, 2, 1)
    return 0.5 * (gradient + transpose), 0.5 * (gradient - transpose)


@register("Q", "velocity_gradient")
def q_criterion(grid, gradient) -> np.ndarray:
    """Q criterion, ``(n_points,)``: ``(|Omega|^2 - |S|^2) / 2`` with Frobenius norms.

    Positive where rotation exceeds strain (inside a vortex), negative where strain
    dominates. Units: velocity gradient squared.
    """
    strain, rotation = strain_and_rotation(gradient)
    return 0.5 * ((rotation ** 2).sum((1, 2)) - (strain ** 2).sum((1, 2)))


@register("lambda2", "velocity_gradient")
def lambda2(grid, gradient) -> np.ndarray:
    """Lambda2 (Jeong and Hussain 1995), ``(n_points,)``.

    The middle eigenvalue of ``S^2 + Omega^2``; **negative** inside a vortex core, so
    isosurfaces are drawn at negative levels. Units: velocity gradient squared.
    """
    strain, rotation = strain_and_rotation(gradient)
    return np.linalg.eigvalsh(strain @ strain + rotation @ rotation)[:, 1]


def _component(index: int, axis: str) -> None:
    @register(f"vorticity_{axis}", "vorticity")
    def component(grid, vorticity) -> np.ndarray:
        return vorticity[:, index]

    component.__doc__ = f"The {axis} component of vorticity, ``(n_points,)``."


for _index, _axis in enumerate("xyz"):
    _component(_index, _axis)
