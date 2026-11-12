"""Small helpers shared by the adapters."""
from __future__ import annotations

import pyvista as pv


def outer_surface(mesh: pv.DataSet) -> pv.PolyData:
    """The outer surface of ``mesh`` with its point data, without VTK's bookkeeping arrays.

    Names the algorithm where pyvista accepts it: its default is announced to change,
    and the films must not change with it.
    """
    try:
        surface = mesh.extract_surface(algorithm="dataset_surface")
    except TypeError:  # pyvista before the keyword existed; this was its only algorithm
        surface = mesh.extract_surface()
    for key in ("vtkOriginalPointIds", "vtkOriginalCellIds"):
        for data in (surface.point_data, surface.cell_data):
            if key in data:
                del data[key]
    return surface


def pick_bodies(name, names, source: str) -> list[str]:
    """The body names ``body(step, name)`` means: all for ``None``, else the one asked.

    Raises ``LookupError`` when the source has no body and ``KeyError`` for an unknown name.
    """
    if not names:
        raise LookupError(f"{source}: the source has no body")
    if name is None:
        return list(names)
    if name not in names:
        raise KeyError(f"{source}: no body {name!r}; bodies: {', '.join(names)}")
    return [name]


def merge_surfaces(surfaces) -> pv.PolyData:
    """Several surfaces as one, points not merged; a single surface is returned as is."""
    surfaces = list(surfaces)
    if len(surfaces) == 1:
        return surfaces[0]
    return pv.merge(surfaces, merge_points=False)
