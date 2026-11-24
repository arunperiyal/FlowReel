"""Get the data of the second tutorial: vortex shedding behind a fixed cylinder.

    python get_data.py [DIR] [--every N] [--box X0 X1 Y0 Y1] [--stand-in]

Downloads Mouad Boudina's "Numerical simulation data of a two-dimensional flow around a
fixed circular cylinder" (Zenodo record 5039610, CC BY 4.0: it may be shown, with
credit), checks each file's checksum, and converts it into what the tutorial reads:

- ``DIR/cylinder_re100/binary/cylinder.<step>.plt``: one Tecplot binary PLT file a
  saved step, brought into a project as a tag with ``flowreel data import plt --path
  DIR/cylinder_re100/binary --tag re100`` (which the script prints);
- ``DIR/cylinder_re100/force.csv``: the force on the cylinder, ``time, fx, fy, mz``,
  copied into the tag's ``series/`` and declared under its body.

``DIR`` defaults to ``cases``: the data stays outside the film's project.

The record's flow file (1.17 GB) is text: ``Re Ur``, then ``Nt N``, then for each of
its 201 steps (t = 400 to 420) the time and N lines ``x y U V p``. It holds nodes
only, no elements, so the nodes are triangulated (the cylinder's inside is left out),
the triangles given a span of 0.1 diameter, as the first tutorial's data is, and each
prism cut into three tetrahedra, the cells a PLT volume zone holds. The cylinder's wall
is a closed surface of triangles, its ends capped. The nodes are the same at every
step (the cylinder is fixed), so the mesh is made once.

``--every N`` keeps every Nth step (default 2: 101 steps, 0.2 apart) and ``--box``
the near wake (default x from -3 to 15, y from -5 to 5, in diameters): about 1 GB in
all. ``--stand-in`` writes a small generated flow in the record's own format and
converts it, for a machine without the network; it is not the real data.

Reference: docs/tutorials/unsteady/data.md.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import shutil
import sys
import urllib.request
from pathlib import Path

RECORD = "https://zenodo.org/records/5039610/files/"
#: The record's files and their SHA-256 (the record gives MD5: fb3135ad... and
#: 9eeb693d..., which these were checked against when they were pinned).
FILES = {
    "fixed_cylinder_atRe100":
        "218099d4f56eaf8c49e34e94c8b30bb580df204d3dd513d92334bb26f2c36996",
    "Re100_fixe00.reactions":
        "0d59e01ffce014670cdb963c88ba1bdd5ae6dd35d6fa79c61bdc68eeb690c54b",
}
FLOW, REACTIONS = FILES
NAME = "cylinder_re100"
SPAN = 0.1                      # the slab's thickness, diameters
EVERY = 2
BOX = (-3.0, 15.0, -5.0, 5.0)   # x0, x1, y0, y1
RADIUS = 0.5                    # the cylinder's, diameters
VARIABLES = ["X", "Y", "Z", "U", "V", "W", "Pressure"]
TET, TRI = 4, 2                 # Tecplot zone types


class ChecksumError(RuntimeError):
    """A download whose SHA-256 is not the one pinned in :data:`FILES`."""


def sha256(path: Path) -> str:
    """The SHA-256 of ``path``, read a megabyte at a time."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, path: Path, expected: str, opener=urllib.request.urlopen,
          say=print) -> bool:
    """Download ``url`` to ``path`` unless it is there with the SHA-256 ``expected``,
    streamed to disk (the flow file is 1.17 GB). Returns ``True`` when it downloaded.
    A download with another checksum is deleted and raises :class:`ChecksumError`."""
    if path.is_file() and sha256(path) == expected:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    say(f"downloading {url}")
    with opener(url, timeout=60) as response, open(part, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    got = sha256(part)
    if got != expected:
        part.unlink()
        raise ChecksumError(f"{url}: SHA-256 {got}, expected {expected}; the file was not "
                            f"kept (it may have been changed or damaged on the way)")
    part.replace(path)
    return True


# ---- the record's text format ----------------------------------------------------------

def read_header(f) -> tuple[float, float, int, int]:
    """``(Re, Ur, steps, nodes)`` from the top of an open flow file."""
    re_, ur = (float(v) for v in f.readline().split())
    f.readline()
    nt, n = (int(v) for v in f.readline().split())
    f.readline()
    return re_, ur, nt, n


def read_steps(f, n_steps: int, n_nodes: int, every: int = 1):
    """``(time, array (n_nodes, 5))`` of every ``every``-th step of an open flow file,
    after its header; the others are skipped without being parsed."""
    import numpy as np
    for k in range(n_steps):
        t = float(f.readline())
        lines = itertools.islice(f, n_nodes)
        if k % every:
            for _ in lines:
                pass
            continue
        yield t, np.loadtxt(lines, dtype=float)


# ---- the mesh --------------------------------------------------------------------------

def mesh(xy, box=BOX, radius: float = RADIUS):
    """The 2D mesh of the nodes ``xy`` inside ``box``: ``(keep, triangles, wall)``.
    ``keep`` are the indices of the nodes used, ``triangles`` (m, 3) into them, counter
    clockwise; ``wall`` the nodes on the cylinder, in order round it. The nodes are
    triangulated whole and the triangles inside the box kept, so the box's edges follow
    the mesh, with no slivers; those inside the cylinder are left out."""
    import numpy as np
    from scipy.spatial import Delaunay
    x, y = xy[:, 0], xy[:, 1]
    tri = Delaunay(xy).simplices                  # all of them, then the box's: a box of
    inside = (x >= box[0]) & (x <= box[1]) & (y >= box[2]) & (y <= box[3])  # nodes alone
    tri = tri[inside[tri].all(axis=1)]            # would have slivers along its edges
    centre = xy[tri].mean(axis=1)
    tri = tri[np.hypot(centre[:, 0], centre[:, 1]) > radius]      # not inside the cylinder
    keep = np.unique(tri)
    index = np.full(len(xy), -1)
    index[keep] = np.arange(len(keep))
    tri, pts = index[tri], xy[keep]
    a, b, c = (pts[tri[:, k]] for k in range(3))
    area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    tri[area < 0] = tri[area < 0][:, [0, 2, 1]]
    r = np.hypot(pts[:, 0], pts[:, 1])
    wall = np.flatnonzero(np.abs(r - radius) < 1e-4 * radius)
    wall = wall[np.argsort(np.arctan2(pts[wall, 1], pts[wall, 0]))]
    return keep, tri, wall


def tetrahedra(tri, n: int):
    """The tetrahedra of the prisms on ``tri`` between the layers ``z-`` (nodes 0..n-1)
    and ``z+`` (n..2n-1): three a prism, cut by the lowest-numbered node of each of its
    side faces, so two prisms cut their shared face alike."""
    import numpy as np
    out = []
    for i, j, k in tri:
        a, b, c = sorted((i, j, k))
        out += [(a, b, c, a + n), (b, c, a + n, b + n), (c, a + n, b + n, c + n)]
    return np.array(out, dtype=np.int64)


def positive(tets, points):
    """``tets`` with their nodes ordered for a positive volume."""
    import numpy as np
    p = points[tets]
    vol = np.einsum("ij,ij->i", np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0])
    tets = tets.copy()
    tets[vol < 0] = tets[vol < 0][:, [0, 2, 1, 3]]
    return tets


def wall_triangles(wall, n: int):
    """The cylinder's surface: its band (two triangles a pair of neighbours on the
    ring) and its two ends, each a fan of triangles from the ring's first node."""
    out = []
    m = len(wall)
    for k in range(m):
        a, b = wall[k], wall[(k + 1) % m]
        out += [(a, b, b + n), (a, b + n, a + n)]
    for k in range(1, m - 1):
        out.append((wall[0], wall[k + 1], wall[k]))                # z- end
        out.append((wall[0] + n, wall[k] + n, wall[k + 1] + n))    # z+ end
    return out


# ---- conversion ------------------------------------------------------------------------

def convert(flow_file: Path, reactions: Path, out: Path, *, every: int = EVERY,
            box=BOX, say=print) -> dict:
    """Write the PLT files and ``force.csv`` (see the module) into ``out``; returns what
    was written: steps, times, nodes, cells."""
    import numpy as np
    from flowreel.sources.plt.writer import write_plt
    binary = out / "binary"
    binary.mkdir(parents=True, exist_ok=True)
    for old in binary.glob("*.plt"):
        old.unlink()
    with open(flow_file) as f:
        _, _, nt, n_nodes = read_header(f)
        times, built = [], None
        for t, data in read_steps(f, nt, n_nodes, every):
            if built is None:
                keep, tri, wall = mesh(data[:, :2], box)
                n = len(keep)
                xy = data[keep, :2]
                z = np.r_[np.full(n, -SPAN / 2), np.full(n, SPAN / 2)]
                points = np.c_[np.tile(xy, (2, 1)), z]
                tets = positive(tetrahedra(tri, n), points)
                surface = np.array(wall_triangles(wall, n), dtype=np.int64)
                built = (keep, n, points, tets, surface)
                say(f"mesh: {n} nodes a layer, {len(tri)} triangles, {len(tets)} tetrahedra, "
                    f"{len(wall)} nodes round the cylinder")
            keep, n, points, tets, surface = built
            u, v, p = (np.tile(data[keep, k], 2) for k in (2, 3, 4))
            step = int(round(t * 10))
            write_plt(binary / f"cylinder.{step}.plt", VARIABLES,
                      [points[:, 0], points[:, 1], points[:, 2], u, v, np.zeros(2 * n), p],
                      [("fluid", TET, tets), ("cylinder", TRI, surface)], time=t)
            times.append(t)
    rows = [line.split()[:4] for line in Path(reactions).read_text().splitlines() if line.strip()]
    lo, hi = times[0], times[-1]
    lines = ["time,fx,fy,mz"] + [",".join(r) for r in rows if lo - 1e-9 <= float(r[0]) <= hi + 1e-9]
    (out / "force.csv").write_text("\n".join(lines) + "\n")
    say(f"converted {len(times)} steps, t = {lo:g} to {hi:g}, into {binary}, and the force "
        f"into {out / 'force.csv'} ({len(lines) - 1} rows)")
    return {"steps": len(times), "first": lo, "last": hi, "nodes": 2 * built[1],
            "cells": len(built[3])}


# ---- a stand-in -------------------------------------------------------------------------

def write_stand_in(folder: Path, n_around: int = 32, n_out: int = 14, steps: int = 161):
    """A small flow and force in the record's own text formats, generated: an O-grid of
    nodes round a cylinder of radius 0.5, the potential flow past it with two rows of
    vortices carried downstream (not a solution of anything), and a lift that swings at
    the shedding frequency. Returns the two files."""
    import numpy as np
    folder.mkdir(parents=True, exist_ok=True)
    r = RADIUS * np.geomspace(1, 30, n_out)
    th = np.linspace(0, 2 * np.pi, n_around, endpoint=False)
    R, T = np.meshgrid(r, th, indexing="ij")
    x, y = (R * np.cos(T)).ravel(), (R * np.sin(T)).ravel()
    times = 400 + 0.1 * np.arange(steps)
    flow = folder / FLOW
    with open(flow, "w") as f:
        f.write("100 1000000.0\n\n%d %d\n\n" % (steps, len(x)))
        for t in times:
            z = x + 1j * y
            w = 1 - RADIUS**2 / np.where(z == 0, 1, z) ** 2                  # potential flow
            for k in range(-2, 12):
                xv = k * 2.5 + (t - 400) * 0.8 % 2.5
                for sign, yv in ((1, 0.4), (-1, -0.4)):
                    zv = xv + 1.25 * (sign < 0) + 1j * yv
                    w += sign * 0.4j / (2 * np.pi) / (z - zv + 0.3)
            u, v = w.real, -w.imag
            u[np.isclose(R.ravel(), RADIUS)] = v[np.isclose(R.ravel(), RADIUS)] = 0
            p = 0.5 * (1 - u**2 - v**2)
            f.write("%.6f\n" % t)
            np.savetxt(f, np.c_[x, y, u, v, p], fmt="%13.9f")
    reactions = folder / REACTIONS
    tr = np.arange(0, times[-1] + 0.05, 0.1)
    fy = 0.3 * np.sin(2 * np.pi * 0.165 * tr)
    reactions.write_text("".join(" %.7E  %.7E %.7E %.7E CYLINDRE_FIXE\n" % (t, 0.66, f_, 0.0)
                                 for t, f_ in zip(tr, fy)))
    return flow, reactions


# ---- the whole ----------------------------------------------------------------------------

README = """# {name}

{what}

- Source: Mouad Boudina, "Numerical simulation data of a two-dimensional flow around a
  fixed circular cylinder", Polytechnique Montréal, 2021, Zenodo record 5039610,
  https://doi.org/10.5281/zenodo.5039610 (solver Cadyf, finite elements, Re = 100).
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0): it may be shown
  and shared, with this credit.
- Converted by FlowReel's examples/tutorial_unsteady/get_data.py: every {every} step(s)
  of t = {first:g} to {last:g}, the near wake x {x0:g} to {x1:g}, y {y0:g} to {y1:g}
  (diameters), given a span of {span:g}; {nodes} nodes and {cells} tetrahedra a file.
"""
REAL = "Vortex shedding behind a fixed cylinder of diameter 1 at a Reynolds number of 100."
STAND_IN = ("**A generated stand-in, not the real data**: the record's formats, a made-up "
            "flow. Run get_data.py without --stand-in for the real one.")


def get(folder: str | Path = "cases", *, every: int = EVERY, box=BOX, stand_in: bool = False,
        opener=urllib.request.urlopen, say=print) -> Path:
    """Download (or generate) and convert the data into ``folder/cylinder_re100``;
    returns that folder. A conversion already there with the same files and options is
    kept."""
    out = Path(folder) / NAME
    record = out / "record"
    if stand_in:
        flow, reactions = write_stand_in(record)
    else:
        for name, expected in FILES.items():
            fetch(RECORD + name + "?download=1", record / name, expected, opener, say)
        flow, reactions = record / FLOW, record / REACTIONS
    stamp = {"stand_in": stand_in, "every": every, "box": list(box), "span": SPAN,
             "sha256": {p.name: sha256(p) for p in (flow, reactions)}}
    done = out / "converted.json"
    try:
        if json.loads(done.read_text()) == stamp and (out / "force.csv").is_file():
            say(f"{out}: converted already; nothing changed")
            say(import_line(out))
            return out
    except (OSError, ValueError):
        pass
    measured = convert(flow, reactions, out, every=every, box=box, say=say)
    (out / "README.md").write_text(README.format(
        name=NAME, what=STAND_IN if stand_in else REAL, every=every, x0=box[0], x1=box[1],
        y0=box[2], y1=box[3], span=SPAN, **measured))
    done.write_text(json.dumps(stamp, indent=2) + "\n")
    say(import_line(out))
    return out


def import_line(out: Path) -> str:
    """The command that brings the case into a project as the tag ``re100``."""
    return f"next, in the project: flowreel data import plt --path {out}/binary --tag re100"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     epilog="Reference: docs/tutorials/unsteady/data.md")
    parser.add_argument("folder", nargs="?", default="cases", metavar="DIR",
                        help="where the case's folder goes (default ./cases)")
    parser.add_argument("--every", type=int, default=EVERY, metavar="N",
                        help=f"keep every Nth step (default {EVERY})")
    parser.add_argument("--box", type=float, nargs=4, default=BOX,
                        metavar=("X0", "X1", "Y0", "Y1"),
                        help="the part of the flow kept, diameters (default %s)" % " ".join(f"{v:g}" for v in BOX))
    parser.add_argument("--stand-in", action="store_true",
                        help="a small generated flow in the record's format, not the real data")
    args = parser.parse_args(argv)
    if args.every < 1:
        parser.error("--every must be at least 1")
    try:
        get(args.folder, every=args.every, box=tuple(args.box), stand_in=args.stand_in)
    except (OSError, ChecksumError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
