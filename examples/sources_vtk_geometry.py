"""The ``vtk`` and ``geometry`` sources on generated data.

Run from a checkout:

    PYTHONPATH=src python examples/sources_vtk_geometry.py

It writes a small VTK series (a decaying vortex around a cylinder) to a temporary folder,
opens it with the ``vtk`` adapter, reads one step whole and cropped, then builds the
grooved cylinder with the ``geometry`` adapter at three stages of carving. Nothing is
rendered and no file is kept.
"""
import tempfile
from pathlib import Path

import numpy as np
import pyvista as pv

from flowreel.box import Box
from flowreel.sources.geometry import GeometrySource
from flowreel.sources.vtk import VtkSource


def write_series(folder: Path, steps=(100, 200, 300)) -> None:
    """Write ``wake_<step>.vtu`` with ``velocity`` and ``pressure``, and ``cylinder.vtp``."""
    for step in steps:
        grid = pv.ImageData(dimensions=(33, 17, 9), spacing=(0.25, 0.25, 0.25),
                            origin=(-2, -2, 0)).cast_to_unstructured_grid()
        x, y, _ = grid.points.T
        strength = np.exp(-step / 400) * np.exp(-(x**2 + y**2))
        grid.point_data["velocity"] = np.column_stack([-y * strength, x * strength, 0 * x])
        grid.point_data["pressure"] = -0.5 * strength**2
        grid.save(folder / f"wake_{step:04d}.vtu")
    pv.Cylinder(center=(0, 0, 1), direction=(0, 0, 1), radius=0.5, height=2).save(
        folder / "cylinder.vtp")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        write_series(folder)

        # Steps come from the filenames; dt turns them into times.
        wake = VtkSource(folder / "wake_*.vtu", body=folder / "cylinder.vtp", dt=0.01)
        print("steps  ", wake.steps())
        print("times  ", [wake.time(s) for s in wake.steps()])
        print("fields ", wake.fields())
        print("bounds ", wake.bounds())

        # The files hold a vector `velocity` and `pressure`; ask for the standard names.
        box = Box((-1, -1, 0), (1, 1, 2))
        whole = wake.flow(200, ["U", "V", "W", "p"], None)
        near = wake.flow(200, ["U", "V", "W", "p"], box)
        print(f"cells   whole {whole.n_cells}, cropped {near.n_cells}")
        print(f"memory  whole {wake.memory_per_step(None) * 1e3:.3f} MB, "
              f"cropped {wake.memory_per_step(box) * 1e3:.3f} MB")
        print("body   ", wake.body(200).n_cells, "faces")

    # A body with no data: the carving shot. build() overrides parameters for one frame,
    # which is how a track will drive `cut_front`.
    carve = GeometrySource("grooved_cylinder", params={"samples": (241, 361)}, frames=3)
    print("geometry steps", carve.steps(), "fields", carve.fields())
    for front in (-0.3, 6.0, 12.3):
        surface = carve.build(cut_front=front)
        cut = float(np.mean(surface["groove"]))
        print(f"cut_front {front:5.1f}: {surface.n_points} points, mean groove {cut:.3f}, "
              f"glowing points {int(np.count_nonzero(surface['fresh']))}")


if __name__ == "__main__":
    main()
