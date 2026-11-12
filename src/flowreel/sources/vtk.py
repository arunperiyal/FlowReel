"""The ``vtk`` adapter: a ``.pvd`` collection or a filename pattern, read with pyvista
(docs/PLAN.md, Section 5.2)."""
from __future__ import annotations

import glob
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pyvista as pv

from flowreel.box import Box
from flowreel.sources.base import PRESSURE, VELOCITY, VELOCITY_COMPONENTS

_WILDCARDS = re.compile(r"[*?\[]")


def _pvd_entries(path: Path) -> list[tuple[float, Path]]:
    """``(time, file)`` of every ``DataSet`` in a ``.pvd`` file, ordered by time."""
    entries = []
    for node in ET.parse(path).getroot().iter("DataSet"):
        entries.append((float(node.get("timestep", len(entries))), path.parent / node.get("file")))
    if not entries:
        raise ValueError(f"{path}: no DataSet entries")
    entries.sort(key=lambda e: e[0])
    times = [t for t, _ in entries]
    if len(set(times)) != len(times):
        raise ValueError(f"{path}: several files share one timestep (parts are not supported; "
                         "point the collection at one file per step, e.g. a .pvtu)")
    return entries


def _pattern_files(pattern: str) -> dict[int, Path]:
    """Files matching ``pattern`` keyed by the number its first wildcard matched."""
    head = _WILDCARDS.split(Path(pattern).name, maxsplit=1)[0]
    regex = re.compile(re.escape(head) + r"(\d+)")
    found: dict[int, Path] = {}
    for name in glob.glob(pattern):
        match = regex.match(Path(name).name)
        if match is None:
            raise ValueError(f"{name}: no step number where the pattern {pattern!r} has its wildcard")
        step = int(match.group(1))
        if step in found:
            raise ValueError(f"{name} and {found[step]} both give step {step}")
        found[step] = Path(name)
    return dict(sorted(found.items()))


def _step_files(path: str | Path, what: str) -> tuple[dict[int, Path], dict[int, float] | None]:
    """Resolve a ``.pvd`` file, a pattern or one file to ``{step: file}`` and pvd times.

    A ``.pvd`` numbers its steps 0, 1, ... in time order and returns their times; a
    pattern takes the step from the filename and returns ``None`` for the times; a single
    file is step 0.
    """
    text = str(path)
    if _WILDCARDS.search(Path(text).name):
        files = _pattern_files(text)
        if not files:
            raise FileNotFoundError(f"no {what} files match {text!r}")
        return files, None
    if not Path(text).is_file():
        raise FileNotFoundError(f"{what} file {text!r} does not exist")
    if text.lower().endswith(".pvd"):
        entries = _pvd_entries(Path(text))
        return ({i: f for i, (_, f) in enumerate(entries)},
                {i: t for i, (t, _) in enumerate(entries)})
    return {0: Path(text)}, None


def _crop(mesh: pv.UnstructuredGrid, box: Box) -> pv.UnstructuredGrid:
    """The cells of ``mesh`` with every node inside ``box``, with their point data."""
    inside = box.contains(mesh.points)
    if inside.all():
        return mesh
    if not inside.any():
        return pv.UnstructuredGrid()
    return mesh.extract_points(inside, adjacent_cells=False, pass_cell_ids=False,
                               pass_point_ids=False)


def _block(data: pv.MultiBlock, key: str | int, where: str):
    """Block ``key`` (a name or an index) of ``data``; nested blocks are merged."""
    names = list(data.keys())
    try:
        block = data[key]
    except (KeyError, IndexError):
        block = None
    if block is None:
        raise KeyError(f"{where}: no block {key!r}; blocks are {names}")
    return block.combine() if isinstance(block, pv.MultiBlock) else block


class VtkSource:
    """A series of VTK files as a :class:`~flowreel.sources.Source`.

    Arguments:
        path: a ``.pvd`` file, a pattern such as ``out/wake_*.vtu``, or one file.
        names: mapping from a standard name (``U``, ``V``, ``W``, ``velocity``, ``p``) to
            the array's name in the files. Without it, ``U``/``V``/``W`` arrays are used
            if present, else a three-component ``velocity`` (or ``U``) array is split;
            pressure is ``p`` or ``pressure``.
        body: the wall surface, as one file (used at every step), a pattern or a ``.pvd``
            (matched to the flow by step number). Volume cells are reduced to their
            outer surface.
        body_block: name or index of the block holding the body, in the ``body`` files
            if given, else in the flow files (which are then multiblock).
        flow_block: name or index of the block holding the flow when the flow files are
            multiblock. Default: the only block that is not ``body_block``.
        dt: time of one step, so ``time = step * dt`` (pattern only; default 1).
        times: the times, either one per step in ascending step order or a mapping
            ``{step: time}``. Overrides ``dt`` and the ``.pvd`` values.
        name: label of the source.

    Steps are 0, 1, ... in time order for a ``.pvd``, and the number in the filename for
    a pattern. Fields are point fields; an array stored on cells is averaged to the
    points. Units and axes are those of the files.
    """

    def __init__(self, path: str | Path, *, names: Mapping[str, str] | None = None,
                 body: str | Path | None = None, body_block: str | int | None = None,
                 flow_block: str | int | None = None,
                 dt: float | None = None,
                 times: Sequence[float] | Mapping[int, float] | None = None,
                 name: str = "vtk"):
        self.name = name
        self.path = str(path)
        self._files, pvd_times = _step_files(path, "flow")
        self._names = dict(names or {})
        self._body_files = None if body is None else _step_files(body, "body")[0]
        self._body_block = body_block
        self._flow_block_key = flow_block
        unknown = set(self._names) - {*VELOCITY_COMPONENTS, VELOCITY, PRESSURE}
        if unknown:
            raise ValueError(f"names: unknown standard name(s) {sorted(unknown)}; "
                             f"use U, V, W, velocity or p")
        self._times = self._resolve_times(pvd_times, dt, times)
        self._arrays: dict[str, int] | None = None
        self._bounds: Box | None = None
        self._memory: dict[Box | None, float] = {}

    # ---- steps and time -------------------------------------------------------------

    def _resolve_times(self, pvd_times, dt, times) -> dict[int, float]:
        steps = list(self._files)
        if times is not None:
            if isinstance(times, Mapping):
                missing = [s for s in steps if s not in times]
                if missing:
                    raise ValueError(f"times: no time for step(s) {missing}")
                return {s: float(times[s]) for s in steps}
            if len(times) != len(steps):
                raise ValueError(f"times: {len(times)} values for {len(steps)} steps")
            return {s: float(t) for s, t in zip(steps, times)}
        if pvd_times is not None:
            if dt is not None:
                return {s: s * float(dt) for s in steps}
            return pvd_times
        return {s: s * (1.0 if dt is None else float(dt)) for s in steps}

    def steps(self) -> list[int]:
        """Saved step numbers, ascending."""
        return list(self._files)

    def time(self, step: int) -> float:
        """Physical time of ``step`` (see the class docstring for where it comes from)."""
        self._check(step)
        return self._times[step]

    def _check(self, step: int) -> None:
        if step not in self._files:
            raise KeyError(f"{self.name}: no step {step}; steps run from "
                           f"{min(self._files)} to {max(self._files)}")

    # ---- reading --------------------------------------------------------------------

    def _read(self, step: int, arrays: Sequence[str] | None) -> pv.UnstructuredGrid:
        """Read the flow of ``step`` with only ``arrays`` (``None`` reads all of them)."""
        reader = pv.get_reader(str(self._files[step]))
        if arrays is not None and hasattr(reader, "disable_all_point_arrays"):
            wanted = set(arrays)
            reader.disable_all_point_arrays()
            reader.disable_all_cell_arrays()
            for a in wanted & set(reader.point_array_names):
                reader.enable_point_array(a)
            for a in wanted & set(reader.cell_array_names):
                reader.enable_cell_array(a)
        mesh = self._flow_block(reader.read())
        if not isinstance(mesh, pv.UnstructuredGrid):
            mesh = mesh.cast_to_unstructured_grid()
        return mesh

    def _flow_block(self, data):
        """The flow part of what a file holds."""
        if not isinstance(data, pv.MultiBlock):
            return data
        if self._flow_block_key is not None:
            return _block(data, self._flow_block_key, self.path)
        names = list(data.keys())
        skip = None
        if self._body_files is None and self._body_block is not None:
            skip = (self._body_block if isinstance(self._body_block, int)
                    else names.index(self._body_block) if self._body_block in names else None)
        rest = [i for i in range(data.n_blocks) if i != skip]
        if len(rest) != 1:
            raise ValueError(f"{self.name}: {self.path} holds the blocks {names}; "
                             "say which is the flow with flow_block")
        return _block(data, rest[0], self.path)

    def _array_sizes(self) -> dict[str, int]:
        """Number of components of every array in the files, read once from the first step."""
        if self._arrays is None:
            mesh = self._read(self.steps()[0], None)
            sizes = {}
            for data in (mesh.cell_data, mesh.point_data):  # point data wins on a clash
                for key in data.keys():
                    arr = data[key]
                    sizes[key] = 1 if arr.ndim == 1 else arr.shape[1]
            self._arrays = sizes
        return self._arrays

    # ---- names ----------------------------------------------------------------------

    def _vector_name(self) -> str | None:
        """Name in the files of the velocity vector, or ``None``."""
        sizes = self._array_sizes()
        if VELOCITY in self._names:
            return self._names[VELOCITY]
        for key, n in sizes.items():
            if n == 3 and key.lower() == VELOCITY:
                return key
        if sizes.get("U") == 3:  # OpenFOAM's convention
            return "U"
        return None

    def _component_name(self, comp: str) -> str | None:
        """Name in the files of the scalar array holding velocity component ``comp``."""
        sizes = self._array_sizes()
        if comp in self._names:
            return self._names[comp]
        return comp if sizes.get(comp) == 1 else None

    def _pressure_name(self) -> str | None:
        sizes = self._array_sizes()
        if PRESSURE in self._names:
            return self._names[PRESSURE]
        if PRESSURE in sizes:
            return PRESSURE
        return next((k for k in sizes if k.lower() == "pressure"), None)

    def _plan(self, field: str) -> tuple[str, ...]:
        """How to build ``field``: the file arrays it needs, as ``(kind, name, ...)``."""
        sizes = self._array_sizes()

        def need(array):
            if array not in sizes:
                raise KeyError(f"{self.name}: array {array!r} (for {field!r}) is not in the "
                               f"files; they hold {sorted(sizes)}")
            return array

        if field in VELOCITY_COMPONENTS:
            scalar = self._component_name(field)
            if scalar is not None:
                return ("array", need(scalar))
            vector = self._vector_name()
            if vector is not None:
                return ("component", need(vector), VELOCITY_COMPONENTS.index(field))
        elif field == VELOCITY:
            vector = self._vector_name()
            if vector is not None:
                return ("array", need(vector))
            scalars = [self._component_name(c) for c in VELOCITY_COMPONENTS]
            if all(s is not None for s in scalars):
                return ("stack", *(need(s) for s in scalars))
        elif field == PRESSURE:
            pressure = self._pressure_name()
            if pressure is not None:
                return ("array", need(pressure))
        elif field in sizes and field not in self._claimed():
            return ("array", field)
        raise KeyError(f"{self.name}: cannot provide {field!r}; available: {self.fields()}")

    def _claimed(self) -> set[str]:
        """File arrays that are served under a standard name instead of their own."""
        claimed = {self._vector_name(), self._pressure_name(),
                   *(self._component_name(c) for c in VELOCITY_COMPONENTS)}
        return claimed - {None}

    def fields(self) -> list[str]:
        """Standard names the files can provide, then the other arrays under their own name."""
        out = []
        for f in (*VELOCITY_COMPONENTS, VELOCITY, PRESSURE):
            try:
                self._plan(f)
            except KeyError:
                continue
            out.append(f)
        claimed = self._claimed()
        return out + sorted(k for k in self._array_sizes() if k not in claimed and k not in out)

    # ---- flow -----------------------------------------------------------------------

    def flow(self, step: int, fields: list[str], crop: Box | None) -> pv.UnstructuredGrid:
        """The volume at ``step`` with exactly ``fields`` as point data, cropped to ``crop``.

        Only the arrays the fields need are read from the file, and the crop is applied
        before the fields are built, so the whole domain is held only for a moment. The
        crop keeps the cells with every node inside the box (edges included).
        A crop that keeps nothing returns an empty grid without arrays (pyvista does not
        hold arrays of length zero).
        """
        self._check(step)
        plans = {f: self._plan(f) for f in fields}
        arrays = sorted({a for plan in plans.values() for a in plan[1:] if isinstance(a, str)})
        mesh = self._read(step, arrays)
        if any(a not in mesh.point_data for a in arrays):
            mesh = mesh.cell_data_to_point_data(pass_cell_data=False)
        if crop is not None:
            mesh = _crop(mesh, crop)
            if mesh.n_points == 0:
                return mesh
        values = {}
        for f, plan in plans.items():
            if plan[0] == "array":
                values[f] = np.asarray(mesh.point_data[plan[1]])
            elif plan[0] == "component":
                values[f] = np.asarray(mesh.point_data[plan[1]])[:, plan[2]]
            else:
                values[f] = np.column_stack([mesh.point_data[a] for a in plan[1:]])
        mesh.clear_data()
        for f in fields:
            mesh.point_data[f] = values[f]
        return mesh

    # ---- size -----------------------------------------------------------------------

    def bounds(self) -> Box:
        """Bounds of the whole domain, taken from the first step."""
        if self._bounds is None:
            self._bounds = Box.from_bounds(self._read(self.steps()[0], []).bounds)
        return self._bounds

    def memory_per_step(self, crop: Box | None) -> float:
        """Estimated memory in GB of one step read with ``crop``.

        Counts the points and cells of the first step that the crop keeps (reading the
        mesh without its arrays), then allows for the coordinates, the connectivity and
        every array of the files as 8-byte values: an upper bound for a request that
        asks for fewer fields. The whole step is in memory for a moment while it is
        cropped; that peak is ``memory_per_step(None)``.
        """
        if crop not in self._memory:
            mesh = self._read(self.steps()[0], [])
            if self._bounds is None:
                self._bounds = Box.from_bounds(mesh.bounds)
            if crop is not None:
                mesh = _crop(mesh, crop)
            per_point = 3 + sum(self._array_sizes().values())
            values = mesh.n_points * per_point + mesh.cells.size + 2 * mesh.n_cells
            self._memory[crop] = 8 * values / 1e9
        return self._memory[crop]

    # ---- body and series ------------------------------------------------------------

    def body(self, step: int) -> pv.PolyData:
        """The wall surface at ``step``, from the ``body`` files or the ``body_block``.

        Raises ``LookupError`` when the source was given neither.
        """
        self._check(step)
        if self._body_files is not None:
            files = self._body_files
            if len(files) == 1:
                file = next(iter(files.values()))
            elif step in files:
                file = files[step]
            else:
                raise KeyError(f"{self.name}: no body file for step {step}")
            data = pv.read(str(file))
            if isinstance(data, pv.MultiBlock):
                data = (_block(data, self._body_block, str(file))
                        if self._body_block is not None else data.combine())
        elif self._body_block is not None:
            file = self._files[step]
            data = pv.read(str(file))
            if not isinstance(data, pv.MultiBlock):
                raise ValueError(f"{self.name}: body_block needs multiblock files, "
                                 f"but {file} is a {type(data).__name__}")
            data = _block(data, self._body_block, str(file))
        else:
            raise LookupError(f"{self.name}: no body; give the source a body file or "
                              "pattern, or a body_block")
        return data if isinstance(data, pv.PolyData) else data.extract_surface()

    def series(self, name: str) -> pd.DataFrame:
        """VTK files carry no time series: always raises ``KeyError``."""
        raise KeyError(f"{self.name}: the vtk adapter has no time series (asked for {name!r})")
