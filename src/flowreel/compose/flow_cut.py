"""Planar cuts of a source's step, for the flow panels (plan Section 9.2).

A **cut** is the flow on a plane normal to one axis: ``Plane(axis, at)``, or the plane
across a body at one of its stations (:func:`station_plane`). :func:`read_cut` reads the
step's volume inside a box around the plane (a slab ``depth`` thick each side, as wide
as the view needs), computes the asked fields on the volume (derived fields need the
gradient across the plane, so they are computed before cutting), cuts it, and returns
a :class:`Cut`: a triangulation in the plane's two axes and the fields at its points.

The box is the source's ``crop``, so a long source read through a window
(the ``plt`` adapter's reader) loads only the nodes near the cut.

The plane's two axes are ``across`` and ``up`` in the picture. By default they are the
other two axes in the order x, y, z (a cut normal to x shows y across and z up);
:func:`plane_axes` takes another order, such as ``[z, y]`` for a flow along z.

Body outlines in the plane (:func:`outlines`), the body's centre (:func:`body_centre`)
and its velocity (:func:`body_velocity`, from its centre at neighbouring steps) are what
a section needs to draw the body and the flow relative to it. Lengths are in the
source's unit, velocities in its velocity unit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from flowreel.box import Box
from flowreel.scene.backend import plain_vtk_filters

plain_vtk_filters()           # the panel cuts with VTK's own filters (see there)

AXES = "xyz"


@dataclass(frozen=True)
class Plane:
    """The plane ``axis = at``: ``axis`` 0, 1 or 2 (x, y, z), ``at`` in length unit."""

    axis: int
    at: float

    def origin(self) -> tuple[float, float, float]:
        """A point of the plane."""
        o = [0.0, 0.0, 0.0]
        o[self.axis] = float(self.at)
        return tuple(o)


def station_plane(axis: str, station: float) -> Plane:
    """The plane across a body whose span runs along ``axis`` (``x``, ``y``, ``z``), at
    ``station`` along it."""
    return Plane(AXES.index(axis), float(station))


def plane_axes(normal: int, given=None) -> tuple[int, int]:
    """The plane's ``(across, up)`` axes: ``given`` (two axis names, neither the
    normal), else the other two in the order x, y, z. ``ValueError`` when wrong."""
    if given is None:
        a, b = (k for k in range(3) if k != normal)
        return a, b
    names = list(given)
    if len(names) != 2 or any(n not in AXES for n in names) or names[0] == names[1]:
        raise ValueError(f"expected two different axes of x, y, z, got {given!r}")
    out = tuple(AXES.index(n) for n in names)
    if normal in out:
        raise ValueError(f"{AXES[normal]} is the cut's normal, so it is not in the plane")
    return out


@dataclass
class Cut:
    """The flow on a plane.

    ``points``: ``(n, 2)``, each point's ``across`` and ``up`` coordinates (the 3D
    axes ``axes``); ``triangles``: ``(m, 3)`` indices into them. ``values``: each
    asked field at the points; ``velocity``: ``(n, 3)``, the flow's velocity there.
    """

    plane: Plane
    axes: tuple[int, int]
    points: np.ndarray
    triangles: np.ndarray
    values: dict = field(default_factory=dict)
    velocity: np.ndarray | None = None

    def triangulation(self):
        """The cut as a matplotlib ``Triangulation``."""
        from matplotlib.tri import Triangulation
        return Triangulation(self.points[:, 0], self.points[:, 1], self.triangles)


def plane_box(plane: Plane, axes: tuple[int, int], lo2, hi2, depth: float) -> Box:
    """The box read for a cut: ``depth`` each side of ``plane``, and from ``lo2`` to
    ``hi2`` (``(across, up)`` pairs) in the plane."""
    lo, hi = [0.0] * 3, [0.0] * 3
    lo[plane.axis], hi[plane.axis] = plane.at - depth, plane.at + depth
    for k, a in enumerate(axes):
        lo[a], hi[a] = float(lo2[k]), float(hi2[k])
    return Box(tuple(lo), tuple(hi))


def source_fields(source, names) -> list[str]:
    """What to read from ``source`` for the fields ``names``: velocity always, ``p``
    when a field needs pressure, and any name the source provides itself."""
    from flowreel.fields.registry import available, resolve
    provided = set(source.fields())
    out = ["U", "V", "W"]
    derived = [n for n in names if n not in provided]
    unknown = [n for n in derived if n not in available()]
    if unknown:
        raise ValueError(f"no field {unknown[0]!r}: the source provides "
                         f"{', '.join(sorted(provided))}, and the derived fields are "
                         f"{', '.join(available())}")
    if derived and "pressure" in resolve(derived) and "p" in provided:
        out.append("p")
    out += [n for n in names if n in provided and n not in out]
    return out


def read_cut(source, step: int, plane: Plane, names, crop: Box | None,
             axes: tuple[int, int] | None = None, params: dict | None = None) -> Cut:
    """The cut of ``step`` by ``plane`` with the fields ``names`` (given by the source
    or derived from velocity and pressure), the volume read inside ``crop``. ``axes``
    are the plane's ``(across, up)`` (:func:`plane_axes`); ``params`` go to the
    derived fields that take them (``rho`` and ``u_inf`` of a pressure coefficient).

    Raises ``ValueError`` when no cell inside ``crop`` crosses the plane (a slab thinner
    than one cell, or a plane outside the data).
    """
    from flowreel import fields
    names = list(names)
    axes = axes or plane_axes(plane.axis)
    flow = source.flow(step, source_fields(source, names), crop)
    where = f"{AXES[plane.axis]} = {plane.at:g}"
    empty = (f"the cut at {where} is empty: no cell read crosses the plane (a cell is "
             "read when it lies wholly in the box); make 'depth' larger than a cell, or "
             "check the station and the window")
    if not flow.n_cells:
        raise ValueError(empty)
    derived = [n for n in names if n not in flow.point_data]
    for name, value in fields.compute(flow, derived, **(params or {})).items():
        flow.point_data[name] = value
    flow.point_data["_velocity"] = np.column_stack([flow["U"], flow["V"], flow["W"]])
    cut = flow.slice(normal=AXES[plane.axis], origin=plane.origin())
    if cut.n_points:
        cut = cut.triangulate().clean()
    if not cut.n_cells:
        raise ValueError(empty)
    points = np.asarray(cut.points, dtype=float)[:, list(axes)]
    triangles = np.asarray(cut.faces).reshape(-1, 4)[:, 1:]
    values = {n: np.asarray(cut[n], dtype=float) for n in names}
    return Cut(plane, tuple(axes), points, triangles, values,
               np.asarray(cut["_velocity"], dtype=float))


def outlines(surface, plane: Plane, axes: tuple[int, int]) -> list[np.ndarray]:
    """The closed curves where ``surface`` crosses ``plane``, each ``(k, 2)`` in the
    plane's ``(across, up)`` coordinates, in order along the curve. Empty when the
    surface does not reach the plane."""
    if surface is None or not surface.n_points:
        return []
    sliced = surface.slice(normal=AXES[plane.axis], origin=plane.origin())
    if not sliced.n_points:
        return []
    lines = sliced.strip(join=True)
    pts = np.asarray(lines.points, dtype=float)[:, list(axes)]
    out, data, i = [], np.asarray(lines.lines), 0
    while i < len(data):
        n = int(data[i])
        ids = data[i + 1:i + 1 + n]
        i += n + 1
        if n >= 3:
            out.append(pts[ids])
    return out


def inside(curves: list[np.ndarray], across, up) -> np.ndarray:
    """Mask of the points ``(across, up)`` (arrays of one shape) inside any curve."""
    from matplotlib.path import Path
    across, up = np.asarray(across, float), np.asarray(up, float)
    flat = np.column_stack([across.ravel(), up.ravel()])
    mask = np.zeros(len(flat), dtype=bool)
    for c in curves:
        mask |= Path(c).contains_points(flat)
    return mask.reshape(across.shape)


def body_centre(source, step: int, name: str | None, axis: str, station: float,
                slab: float | None = None) -> np.ndarray:
    """``(3,)``: the centre of body ``name``'s section at ``station`` at ``step``."""
    from flowreel.project.measure import centre
    return np.asarray(centre(source.body(step, name), station, axis, slab), dtype=float)


def body_velocity(source, step: int, name: str | None, axis: str, station: float,
                  slab: float | None = None) -> np.ndarray:
    """``(3,)``: the velocity of body ``name``'s section at ``station`` at ``step``,
    from its centre at the saved steps either side (a centred difference; one-sided at
    the first and last step, zero when there is one step)."""
    steps = list(source.steps())
    k = steps.index(step)
    a, b = steps[max(k - 1, 0)], steps[min(k + 1, len(steps) - 1)]
    if a == b:
        return np.zeros(3)
    ca = body_centre(source, a, name, axis, station, slab)
    cb = body_centre(source, b, name, axis, station, slab)
    return (cb - ca) / (source.time(b) - source.time(a))
