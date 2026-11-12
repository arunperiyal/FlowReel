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
