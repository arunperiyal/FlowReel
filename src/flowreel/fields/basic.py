"""Fields taken directly from velocity and pressure: speed, relative velocity, Cp."""
from __future__ import annotations

import numpy as np

from flowreel.fields.registry import register


def dynamic_pressure(rho: float, u_inf: float) -> float:
    """Reference dynamic pressure ``q = rho * u_inf**2 / 2``; must be positive."""
    q = 0.5 * float(rho) * float(u_inf) ** 2
    if not q > 0:
        raise ValueError(f"dynamic pressure must be positive (rho={rho}, u_inf={u_inf})")
    return q


@register("speed", "velocity")
def speed(grid, velocity) -> np.ndarray:
    """Velocity magnitude, ``(n_points,)``, in the velocity unit; never negative."""
    return np.linalg.norm(velocity, axis=1)


@register("velocity_relative", "velocity")
def velocity_relative(grid, velocity, *, body_velocity) -> np.ndarray:
    """Velocity seen from the body: ``velocity - body_velocity``, ``(n_points, 3)``.

    ``body_velocity``: the body's velocity in the same frame and unit, as one ``(3,)``
    vector (rigid translation) or an ``(n_points, 3)`` array.
    """
    body = np.asarray(body_velocity, dtype=float)
    if body.shape not in ((3,), velocity.shape):
        raise ValueError(f"body_velocity must have shape (3,) or {velocity.shape}, "
                         f"not {body.shape}")
    return velocity - body


@register("pressure_coefficient", "pressure")
def pressure_coefficient(grid, pressure, *, rho, u_inf, p_inf=0.0) -> np.ndarray:
    """Pressure coefficient ``(p - p_inf) / q``, ``(n_points,)``, with ``q = rho u_inf^2 / 2``.

    ``rho``: density; ``u_inf``: free-stream speed; ``p_inf``: free-stream pressure
    (default 0), all in the source's units. 1 at a stagnation point of steady inviscid
    flow, negative where the pressure is below the free stream's (suction).
    """
    return (pressure - float(p_inf)) / dynamic_pressure(rho, u_inf)
