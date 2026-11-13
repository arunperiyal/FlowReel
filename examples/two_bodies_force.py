"""Two bodies of any shape in one source, and the force on each.

Run from a checkout:

    PYTHONPATH=src python examples/two_bodies_force.py

It writes a small FlexFlow-style PLT file to a temporary folder: a unit cube of
tetrahedra with a shear flow ``U = s z`` and two walls, the floor (triangles, "plate") and
the ceiling (quadrilaterals, "lid"). The ``flexflow`` adapter finds the zones itself; the
total force on each wall is then ``mu s`` times its area, along +x on the floor and -x on
the ceiling. Nothing is rendered and no file is kept.
"""
import tempfile
from pathlib import Path

import numpy as np

from flowreel import fields
from flowreel.sources.flexflow import FlexflowSource
from flowreel.sources.flexflow.plt_write import write_plt

N, SHEAR, MU = 6, 2.0, 0.1


def node(i, j, k):
    return (k * (N + 1) + j) * (N + 1) + i


def write_case(folder: Path) -> None:
    """Write ``flow.1.plt``: the cube, its velocity and pressure, and the two walls."""
    g = np.arange(N + 1) / N
    z, y, x = (a.ravel() for a in np.meshgrid(g, g, g, indexing="ij"))
    r = range(N)
    bricks = np.array([[node(i, j, k), node(i + 1, j, k), node(i + 1, j + 1, k),
                        node(i, j + 1, k), node(i, j, k + 1), node(i + 1, j, k + 1),
                        node(i + 1, j + 1, k + 1), node(i, j + 1, k + 1)]
                       for k in r for j in r for i in r])
    split = [(0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)]
    tets = np.concatenate([bricks[:, s] for s in split])
    floor = np.array([[node(i, j, 0), node(i + 1, j, 0), node(i + 1, j + 1, 0),
                       node(i, j + 1, 0)] for j in r for i in r])
    plate = np.concatenate([floor[:, [0, 1, 2]], floor[:, [0, 2, 3]]])
    lid = floor + N * (N + 1) ** 2
    write_plt(folder / "flow.1.plt", ["X", "Y", "Z", "U", "V", "W", "Pressure"],
              [x, y, z, SHEAR * z, 0 * x, 0 * x, 0 * x],
              [("fluid", 4, tets), ("plate", 2, plate), ("lid", 3, lid)])


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        write_case(Path(tmp))
        src = FlexflowSource(tmp)
        print(f"volume zone: {src.volume}; bodies: {src.bodies()}")
        flow = src.flow(1, ["U", "V", "W", "p"], None)
        for name in src.bodies():
            wall = src.body(1, name)
            load = fields.compute(flow, "wall_force", wall=wall, mu=MU)["wall_force"]
            print(f"{name}: {wall.n_cells} cells, force on it = {np.round(load.force, 6)}"
                  f" (exact x: {MU * SHEAR * (1 if name == 'plate' else -1):+.6f})")


if __name__ == "__main__":
    main()
