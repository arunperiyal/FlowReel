"""Get the tutorial's data: pyvista's ``cylinder_crossflow``, made ready for FlowReel.

    python examples/tutorial/get_data.py [DIR]               download and convert
    python examples/tutorial/get_data.py [DIR] --stand-in    a small generated copy, offline

The files go in ``DIR/data/cylinder_crossflow/`` (``DIR`` defaults to the current
folder, the tutorial's project folder). The script:

1. Downloads the EnSight case (five files, 0.7 MB) and its licence from the
   ``pyvista/data`` repository, at a fixed commit. It checks each file's SHA-256, and
   refuses (and deletes) a file whose checksum is wrong. Files already there with the
   right checksum are not downloaded again.
2. Converts the case for FlowReel. The flow is one steady 2D step, and FlowReel's layers
   expect cells with volume. So the 2D mesh is given a thin span: one cell across, 0.1
   diameter wide, centred on z = 0. Triangles become wedges and quadrilaterals become
   hexahedra. The velocity is split into ``U``, ``V``, ``W`` and the pressure is stored
   as ``p``. The solver's ``vorticity_mag`` is dropped: FlowReel derives every field
   from velocity and pressure (docs/fields.md). The wall ``wall_cylinder`` is extruded
   the same way into the surface ``cylinder.vtp``.
3. Writes ``LICENSE`` and ``README.md`` beside the data, saying where it comes from and
   how to cite it.

The result, read with ``vtk:data/cylinder_crossflow/flow.pvd`` and the body
``data/cylinder_crossflow/cylinder.vtp``, is:

    data/cylinder_crossflow/
        ensight/       the downloaded case, as published
        flow.pvd       one step (time 0), pointing at flow_0.vtu
        flow_0.vtu     the flow, extruded: U, V, W, p
        cylinder.vtp   the wall, extruded
        LICENSE        Apache-2.0, the licence of pyvista/data
        README.md      source, author, citation, checksums

``--stand-in`` writes a small case in the same format, with the same names, blocks and
fields, and converts it the same way. It is potential flow past a cylinder on a coarse
mesh, not the real data, so tests and a first try need no network.

A second run changes nothing: the conversion is redone only when the downloaded files
have changed. This matters because FlowReel's frame keys include each data file's
modification time, so rewriting the same data would cause every frame to be drawn again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import urllib.request
from pathlib import Path

#: The pyvista/data commit the files are taken from (the last change to the data set).
COMMIT = "f114d31d"
BASE = f"https://raw.githubusercontent.com/pyvista/data/{COMMIT}/"
FOLDER = "Data/EnSight/CylinderCrossflow/"
#: Every file downloaded, with its SHA-256.
FILES = {
    "cylinder_Re35.case": "683956c15c786730bf07596a2a8480eb1de091ba81c57fde6d656f63f1520a32",
    "cylinder_Re35.geo": "5c58108fdb00d5ff306f9b594c423f1634e700197ac0cde9312deab7d8a58dda",
    "cylinder_Re35.scl1": "c489f3af25ce0df23e24933da47aecd3bb64a964f364856e1efe18a54f03f2da",
    "cylinder_Re35.scl2": "c5713b63c643c0f9de20c6a1135de9f383740f8eb33fd430db552b85a9aaa2f5",
    "cylinder_Re35.vel": "aa21f382ea6b189f2b18bf871d6f1352c64b772ad18584b87828ba0ab81cf9b2",
}
LICENSE_URL = BASE + "LICENSE"
LICENSE_SHA256 = "b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1"
NAME = "cylinder_crossflow"
CASE = "cylinder_Re35.case"
#: Span of the extruded mesh, in diameters.
SPAN = 0.1
#: Cell types: VTK's numbers.
TRIANGLE, QUAD, WEDGE, HEXAHEDRON, LINE = 5, 9, 13, 12, 3


class ChecksumError(RuntimeError):
    """A downloaded file is not the one published."""


def sha256(path: Path) -> str:
    """The SHA-256 of the file at ``path``, as hex."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url: str, path: Path, expected: str, opener=urllib.request.urlopen) -> bool:
    """Download ``url`` to ``path`` unless it is already there with the SHA-256
    ``expected``. Returns ``True`` when it downloaded. A download with another checksum
    is deleted, and raises :class:`ChecksumError`."""
    if path.is_file() and sha256(path) == expected:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with opener(url, timeout=60) as response:
        part.write_bytes(response.read())
    got = sha256(part)
    if got != expected:
        part.unlink()
        raise ChecksumError(f"{url}: SHA-256 {got}, expected {expected}; the file was not "
                            f"kept (it may have been changed or damaged on the way)")
    part.replace(path)
    return True


# ---- conversion ----------------------------------------------------------------------

def _extrude_flow(fluid, span: float):
    """``fluid`` (a 2D grid of triangles and quadrilaterals at z = 0) as a grid of
    wedges and hexahedra from z = -span/2 to span/2, with ``U``, ``V``, ``W`` and ``p``
    on both layers of points."""
    import numpy as np
    import pyvista as pv
    pts = np.asarray(fluid.points, float)
    n = len(pts)
    bottom, top = pts.copy(), pts.copy()
    bottom[:, 2], top[:, 2] = -span / 2, span / 2
    cells, types = [], []
    for i in range(fluid.n_cells):
        ids = list(fluid.get_cell(i).point_ids)
        xy = pts[ids, :2]
        area = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1])
        if area < 0:                                   # counter-clockwise seen from +z
            ids = ids[::-1]
        up = [j + n for j in ids]
        if len(ids) == 3:   # VTK's wedge: the base, seen from the top, is clockwise
            cells += [6, ids[0], ids[2], ids[1], up[0], up[2], up[1]]
            types.append(WEDGE)
        elif len(ids) == 4:
            cells += [8, *ids, *up]
            types.append(HEXAHEDRON)
        else:
            raise ValueError(f"fluid cell {i} has {len(ids)} points; expected 3 or 4")
    grid = pv.UnstructuredGrid(np.array(cells), np.array(types, np.uint8), np.vstack([bottom, top]))
    velocity = np.asarray(fluid.point_data["velocity"], float)
    for k, comp in enumerate("UVW"):
        grid.point_data[comp] = np.tile(velocity[:, k], 2)
    grid.point_data["p"] = np.tile(np.asarray(fluid.point_data["pressure"], float), 2)
    return grid


def _extrude_wall(wall, span: float):
    """``wall`` (line segments at z = 0) as a surface of quadrilaterals across the span."""
    import numpy as np
    import pyvista as pv
    pts = np.asarray(wall.points, float)
    n = len(pts)
    bottom, top = pts.copy(), pts.copy()
    bottom[:, 2], top[:, 2] = -span / 2, span / 2
    faces = []
    for i in range(wall.n_cells):
        a, b = wall.get_cell(i).point_ids
        faces += [4, a, b, b + n, a + n]
    return pv.PolyData(np.vstack([bottom, top]), faces=np.array(faces))


def convert(case: Path, out: Path) -> dict:
    """Convert the EnSight ``case`` to ``out/flow.pvd``, ``out/flow_0.vtu`` and
    ``out/cylinder.vtp`` (see the module). Returns what it measured: the diameter, the
    span, and the numbers of points and cells."""
    import pyvista as pv
    data = pv.get_reader(str(case)).read()
    names = list(data.keys())
    for block in ("fluid", "wall_cylinder"):
        if block not in names:
            raise ValueError(f"{case}: no block {block!r} (blocks: {', '.join(names)})")
    fluid = data["fluid"].cast_to_unstructured_grid()
    for array in ("velocity", "pressure"):
        if array not in fluid.point_data:
            raise ValueError(f"{case}: fluid has no {array!r} on its points")
    wall = data["wall_cylinder"]
    x0, x1, y0, y1, _, _ = wall.bounds
    diameter = max(x1 - x0, y1 - y0)
    span = round(SPAN * round(diameter, 2), 6)
    flow = _extrude_flow(fluid, span)
    body = _extrude_wall(wall, span)
    out.mkdir(parents=True, exist_ok=True)
    flow.save(out / "flow_0.vtu")
    body.save(out / "cylinder.vtp")
    (out / "flow.pvd").write_text(
        '<?xml version="1.0"?>\n'
        '<VTKFile type="Collection" version="0.1">\n  <Collection>\n'
        '    <DataSet timestep="0" file="flow_0.vtu"/>\n  </Collection>\n</VTKFile>\n')
    return {"diameter": round(diameter, 4), "span": span, "points": flow.n_points,
            "cells": flow.n_cells, "wall faces": body.n_cells}


# ---- the stand-in ----------------------------------------------------------------------

def _ensight_text(f, text: str):
    f.write(text.encode("ascii").ljust(80, b"\0")[:80])


def write_stand_in(folder: Path, n_around: int = 48, n_out: int = 10) -> Path:
    """Write a small EnSight Gold case like ``cylinder_Re35`` into ``folder``: the same
    file and block names, the same fields on the points, the same domain and cylinder.

    The mesh is an O-grid from the cylinder (diameter 1, centre (2.5, 0)) to the edge of
    the domain (x 0 to 15, y -3.75 to 3.75): ``n_around`` cells around and ``n_out``
    rings outwards. The rings are quadrilaterals, except the outermost ring, whose
    quadrilaterals are split into triangles so that both kinds of cell are converted. The
    flow is potential flow past the cylinder at 35 units of speed: no wake, but a
    velocity and a pressure that vary over the whole domain. Returns the ``.case`` file."""
    import numpy as np
    cx, r, speed = 2.5, 0.5, 35.0
    x0, x1, y0, y1 = 0.0, 15.0, -3.75, 3.75
    theta = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    direction = np.stack([np.cos(theta), np.sin(theta)], 1)
    # where a ray from the centre leaves the domain
    with np.errstate(divide="ignore"):
        tx = np.where(direction[:, 0] > 0, (x1 - cx) / direction[:, 0], (x0 - cx) / direction[:, 0])
        ty = np.where(direction[:, 1] > 0, y1 / direction[:, 1], y0 / direction[:, 1])
    edge = np.array([cx, 0]) + direction * np.minimum(np.abs(tx), np.abs(ty))[:, None]
    wall = np.array([cx, 0]) + r * direction
    s = (np.linspace(0, 1, n_out + 1) ** 1.6)[:, None, None]       # finer near the wall
    xy = ((1 - s) * wall[None] + s * edge[None]).reshape(-1, 2)        # ring by ring
    pts = np.column_stack([xy, np.zeros(len(xy))]).astype(np.float32)

    def at(ring, k):
        return ring * n_around + k % n_around
    quads, tris = [], []
    for ring in range(n_out):
        for k in range(n_around):
            cell = [at(ring, k), at(ring, k + 1), at(ring + 1, k + 1), at(ring + 1, k)]
            if ring == n_out - 1:
                tris += [cell[:3], [cell[0], cell[2], cell[3]]]
            else:
                quads.append(cell)
    wall_bars = [[at(0, k), at(0, k + 1)] for k in range(n_around)]
    outer = [[at(n_out, k), at(n_out, k + 1)] for k in range(n_around)]
    sides = {"inlet": [], "outlet": [], "outlet_top": [], "outlet_bottom": []}
    for a, b in outer:
        mx, my = (pts[a, :2] + pts[b, :2]) / 2
        gaps = {"inlet": mx - x0, "outlet": x1 - mx, "outlet_top": y1 - my, "outlet_bottom": my - y0}
        sides[min(gaps, key=gaps.get)].append([a, b])

    # potential flow past a cylinder: u - i v = U (1 - r^2 / z^2), Bernoulli for p
    z = (pts[:, 0] - cx) + 1j * pts[:, 1]
    w = speed * (1 - r ** 2 / z ** 2)
    velocity = np.column_stack([w.real, -w.imag, np.zeros(len(z))])
    pressure = 0.5 * (speed ** 2 - (velocity ** 2).sum(1))
    vorticity = np.zeros(len(z))

    parts = [("fluid", np.arange(len(pts)), [("quad4", quads), ("tria3", tris)])]
    for name, bars in [*sides.items(), ("wall_cylinder", wall_bars)]:
        parts.append((name, np.unique(np.array(bars)), [("bar2", bars)]))

    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / "cylinder_Re35"
    with open(f"{stem}.geo", "wb") as f:
        for line in ("C Binary", "FlowReel stand-in for cylinder_crossflow", "not real data",
                     "node id assign", "element id assign"):
            _ensight_text(f, line)
        for number, (name, nodes, elements) in enumerate(parts, 1):
            local = {g: i for i, g in enumerate(nodes)}
            _ensight_text(f, "part")
            f.write(struct.pack("<i", number))
            _ensight_text(f, name)
            _ensight_text(f, "coordinates")
            f.write(struct.pack("<i", len(nodes)))
            for axis in range(3):
                f.write(pts[nodes, axis].astype("<f4").tobytes())
            for kind, conn in elements:
                if not conn:
                    continue
                _ensight_text(f, kind)
                f.write(struct.pack("<i", len(conn)))
                f.write((np.array([[local[g] for g in c] for c in conn]) + 1).astype("<i4").tobytes())

    def variable(path, title, values):
        with open(path, "wb") as f:
            _ensight_text(f, title)
            for number, (_, nodes, _) in enumerate(parts, 1):
                _ensight_text(f, "part")
                f.write(struct.pack("<i", number))
                _ensight_text(f, "coordinates")
                v = values[nodes]
                for column in (v.T if v.ndim == 2 else [v]):
                    f.write(column.astype("<f4").tobytes())
    variable(f"{stem}.scl1", "Static Pressure", pressure)
    variable(f"{stem}.scl2", "Vorticity Magnitude", vorticity)
    variable(f"{stem}.vel", "Velocity", velocity)
    case = folder / CASE
    case.write_text(
        "FORMAT\ntype:  ensight gold\nGEOMETRY\nmodel: cylinder_Re35.geo\nVARIABLE\n"
        "scalar per node: pressure cylinder_Re35.scl1\n"
        "scalar per node: vorticity_mag cylinder_Re35.scl2\n"
        "vector per node: velocity cylinder_Re35.vel\n")
    return case


# ---- licence and README ------------------------------------------------------------------

README = """# cylinder_crossflow

{what}

- **Source:** pyvista's example data, `pyvista.examples.download_cylinder_crossflow()`;
  the files are `{folder}` in https://github.com/pyvista/data at commit `{commit}`.
- **Made by:** Matthew Flamm, who added it to pyvista/data in June 2021
  (https://github.com/pyvista/data/pull/2). It was exported from ANSYS Fluent 20.1 as
  EnSight Gold. In his words it "was not generated with accuracy as the goal, e.g.
  predicting drag coefficient, and was not validated in any way". It is good for
  pictures, not for numbers.
- **Licence:** Apache-2.0, the licence of the pyvista/data repository (`LICENSE`, beside
  this file). It allows the data to be copied, changed and shown, in a film too,
  provided the licence and this notice go with any copy of the data.
- **Cite as:** cylinder in crossflow at Re 35, by Matthew Flamm, from the PyVista example
  data (https://github.com/pyvista/data), Apache-2.0. For PyVista itself: Sullivan and
  Kaszynski (2019), "PyVista: 3D plotting and mesh analysis through a streamlined
  interface for the Visualization Toolkit (VTK)", Journal of Open Source Software 4(37),
  1450, https://doi.org/10.21105/joss.01450.

## What was changed

`ensight/` holds the files as published. FlowReel reads the converted files made from
them by `examples/tutorial/get_data.py`:

- `flow.pvd` and `flow_0.vtu`: the block `fluid`, given a span of {span} (one cell,
  {span_d} diameter) centred on z = 0; `velocity` split into `U`, `V`, `W`; `pressure`
  as `p`; `vorticity_mag` left out.
- `cylinder.vtp`: the block `wall_cylinder`, extruded the same way.

{facts}

## Checksums (SHA-256)

{sums}
"""

REAL = ("One steady step of a 2D flow past a cylinder of diameter 1 at a Reynolds number "
        "of 35: the wake holds two vortices attached behind the cylinder and does not shed.")
STAND_IN = ("**A generated stand-in, not the real data.** It has the names, blocks and "
            "fields of pyvista's `cylinder_crossflow`, on a coarse mesh, with potential "
            "flow past the cylinder (no wake). It was written by `get_data.py --stand-in` "
            "so the tutorial can be tried and tested without the network. What is said "
            "below about the source is about the real data set.")


def _write_notes(out: Path, ensight: Path, measured: dict, stand_in: bool):
    sums = "\n".join(f"- `ensight/{name}`: `{sha256(ensight / name)}`" for name in FILES)
    facts = (f"Converted: {measured['points']} points, {measured['cells']} cells; the "
             f"cylinder's diameter measured as {measured['diameter']}.")
    (out / "README.md").write_text(README.format(
        what=STAND_IN if stand_in else REAL, folder=FOLDER, commit=COMMIT,
        span=measured["span"], span_d=SPAN, facts=facts, sums=sums))


def get(folder: str | Path = ".", *, stand_in: bool = False, opener=urllib.request.urlopen,
        say=print) -> Path:
    """Put the tutorial data in ``folder/data/cylinder_crossflow/`` (see the module) and
    return that folder. With ``stand_in``, generate the small copy instead of
    downloading. ``opener`` opens a URL (``urllib.request.urlopen``; tests pass
    another)."""
    out = Path(folder) / "data" / NAME
    ensight = out / "ensight"
    if stand_in:
        stamp_old = _stamp(out)
        if stamp_old is None or stamp_old.get("stand_in") is not True:
            write_stand_in(ensight)
            (out / "LICENSE").write_text(
                "The stand-in was generated by FlowReel's examples/tutorial/get_data.py and\n"
                "is under FlowReel's licence (MIT). The real data set is under Apache-2.0.\n")
            say(f"wrote a stand-in case in {ensight}")
        else:
            say(f"{ensight}: the stand-in is there already")
    else:
        old = _stamp(out)
        if old is not None and old.get("stand_in"):
            raise RuntimeError(f"{out} holds the stand-in; remove the folder to download "
                               f"the real data set")
        got = [name for name in FILES
               if fetch(BASE + FOLDER + name, ensight / name, FILES[name], opener)]
        if fetch(LICENSE_URL, out / "LICENSE", LICENSE_SHA256, opener):
            got.append("LICENSE")
        say(f"downloaded {', '.join(got)}" if got else
            f"{ensight}: all files there already, with the right checksums")
    sums = {name: sha256(ensight / name) for name in FILES}
    stamp = {"stand_in": stand_in, "span": SPAN, "sha256": sums}
    if _stamp(out) == stamp and all((out / f).is_file() for f in
                                    ("flow.pvd", "flow_0.vtu", "cylinder.vtp", "README.md")):
        say(f"{out}: converted already; nothing changed")
        return out
    measured = convert(ensight / CASE, out)
    _write_notes(out, ensight, measured, stand_in)
    (out / "converted.json").write_text(json.dumps(stamp, indent=2) + "\n")
    say(f"converted to {out}/flow.pvd ({measured['points']} points, {measured['cells']} "
        f"cells, span {measured['span']}) and {out}/cylinder.vtp")
    return out


def _stamp(out: Path) -> dict | None:
    try:
        return json.loads((out / "converted.json").read_text())
    except (OSError, ValueError):
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     epilog="Reference: docs/tutorial/data.md")
    parser.add_argument("folder", nargs="?", default=".", metavar="DIR",
                        help="the project folder (default the current one)")
    parser.add_argument("--stand-in", action="store_true",
                        help="generate a small copy instead of downloading (no network)")
    args = parser.parse_args(argv)
    try:
        get(args.folder, stand_in=args.stand_in)
    except (ChecksumError, RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
