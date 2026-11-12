"""The ``flexflow`` source: a FlexFlow case folder read with FlowReel's own PLT reader."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv

from flowreel.box import Box
from flowreel.sources.flexflow.plt import NPE, PltFile
from flowreel.sources.flexflow.series import SERIES

#: FlexFlow's variable names for the standard ones.
NAMES = {"U": "U", "V": "V", "W": "W", "p": "Pressure"}
#: Stored derived fields, never provided: they are nodal sums that depend on the mesh
#: (docs/PLAN.md, Section 6). Compute them with flowreel.fields instead.
NOT_PROVIDED = ("xVor", "yVor", "zVor", "QCriterion")
_CELL = {(3, 4): pv.CellType.QUAD, (2, 3): pv.CellType.TRIANGLE,
         (4, 4): pv.CellType.TETRA, (5, 8): pv.CellType.HEXAHEDRON}


class FlexflowSource:
    """A FlexFlow case.

    Arguments:
        path: the case folder. PLT files are looked for in ``path/binary`` and then in
            ``path`` itself, named ``<anything>.<step>.plt``.
        volume: name of the volume zone (default ``FIELD``).
        body: name of the wall zone (default ``cyl``).
        nen: nodes per element of the volume zone, to override a wrong zone type
            (see the reader); ``None`` trusts the file.
        name: label of the source.

    Coordinates in the files are the deformed mesh, so ``flow`` and ``body`` are already at
    the step's position. Time is the solution time stored in each file.
    """

    def __init__(self, path, volume: str = "FIELD", body: str = "cyl",
                 nen: int | None = None, name: str = "flexflow"):
        self.name = name
        self.path = Path(path)
        self.volume, self.body_zone, self.nen = volume, body, nen
        folder = self.path / "binary" if (self.path / "binary").is_dir() else self.path
        self._files = {}
        for f in folder.glob("*.plt"):
            m = re.search(r"\.(\d+)\.plt$", f.name)
            if m:
                self._files[int(m.group(1))] = f
        if not self._files:
            raise FileNotFoundError(f"no <name>.<step>.plt files in {folder}")

    def _open(self, step: int) -> PltFile:
        try:
            return PltFile(self._files[step])
        except KeyError:
            raise KeyError(f"step {step} is not saved in {self.path}; "
                           f"steps: {self.steps()}") from None

    def steps(self) -> list[int]:
        """Saved step numbers, ascending."""
        return sorted(self._files)

    def time(self, step: int) -> float:
        """Solution time stored in the step's file."""
        with self._open(step) as plt:
            return plt.zones[plt.zone_index(self.volume)]["time"]

    def fields(self) -> list[str]:
        """``U``, ``V``, ``W``, ``p`` and the solver's other stored variables, without
        the stored vorticity and Q."""
        with self._open(self.steps()[0]) as plt:
            raw = [v for v in plt.vars[3:] if v not in NOT_PROVIDED]
        back = {v: k for k, v in NAMES.items()}
        return [back.get(v, v) for v in raw]

    def _check(self, fields):
        unknown = [f for f in fields if f not in self.fields()]
        if unknown:
            raise KeyError(f"flexflow source has no field {unknown}; it provides {self.fields()}")

    def flow(self, step: int, fields: list[str], crop: Box | None) -> pv.UnstructuredGrid:
        """The volume zone with ``fields``; ``crop`` keeps cells with every node inside.

        Only the coordinates and the requested variables are read from the file.
        """
        self._check(fields)
        with self._open(step) as plt:
            zi = plt.zone_index(self.volume)
            conn = plt.load_connectivity(zi, nen=self.nen)
            points = np.column_stack([plt.read_variable(zi, v) for v in plt.vars[:3]])
            data = {f: plt.read_variable(zi, NAMES.get(f, f)) for f in fields}
            ztype = plt.zones[zi]["ztype"]
        if crop is not None:
            conn = conn[crop.contains(points)[conn].all(axis=1)]
        return _grid(points, conn, data, ztype)

    def body(self, step: int) -> pv.PolyData:
        """The wall zone as a surface at the step's position, carrying every provided
        field as point data."""
        with self._open(step) as plt:
            zi = plt.zone_index(self.body_zone)
            conn = plt.load_connectivity(zi)
            points = np.column_stack([plt.read_variable(zi, v) for v in plt.vars[:3]])
            data = {f: plt.read_variable(zi, NAMES.get(f, f)) for f in self.fields()}
            ztype = plt.zones[zi]["ztype"]
        return _grid(points, conn, data, ztype).extract_surface(
            algorithm="dataset_surface", pass_pointid=False, pass_cellid=False)

    def bounds(self) -> Box:
        """Bounds of the volume zone at the first step, from the file header."""
        with self._open(self.steps()[0]) as plt:
            mm = plt.minmax(plt.zone_index(self.volume))
            lo, hi = zip(*(mm[v] for v in plt.vars[:3]))
        return Box(lo, hi)

    def series(self, name: str) -> pd.DataFrame:
        """``displacement`` (OTHD probes) or ``force`` (OISD total force); see
        :mod:`flowreel.sources.flexflow.series` for the columns."""
        if name not in SERIES:
            raise KeyError(f"flexflow source has no series {name!r}; it has {sorted(SERIES)}")
        return SERIES[name](self.path)

    def memory_per_step(self, crop: Box | None) -> float:
        """Rough GB to hold one step with velocity and pressure: float32 coordinates and
        four fields, int64 connectivity, doubled for the VTK copy. The file is read whole
        before cropping, so ``crop`` does not lower the estimate."""
        with self._open(self.steps()[0]) as plt:
            z = plt.zones[plt.zone_index(self.volume)]
            npe = self.nen or NPE.get(z["ztype"], 8)
            return 2 * (z["npts"] * 7 * 4 + z["nelem"] * (npe + 1) * 8) / 1e9


def _grid(points, conn, data, ztype) -> pv.UnstructuredGrid:
    """A grid of the nodes the cells use, renumbered, with ``data`` as point arrays."""
    used = np.unique(conn)
    remap = np.full(len(points), -1, np.int64)
    remap[used] = np.arange(len(used))
    cell = _CELL[(ztype, conn.shape[1])]
    grid = pv.UnstructuredGrid({cell: remap[conn]}, points[used].astype(np.float64))
    for name, values in data.items():
        if values is not None:
            grid.point_data[name] = values[used]
    return grid

