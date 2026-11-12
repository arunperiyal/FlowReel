"""Writer for the Tecplot binary layout FlexFlow writes (TDV112, block data, float32).

Used to cut small test files out of solver output (``tools/cut_plt.py``) and to generate
synthetic files for tests. It writes what :class:`~flowreel.sources.flexflow.plt.PltFile`
reads: one zone storing every variable on the nodes, and any number of further zones
that share those arrays and bring only their own connectivity (the way FlexFlow writes a
wall zone next to the volume zone).
"""
from __future__ import annotations

import struct

import numpy as np

from flowreel.sources.flexflow.plt import NPE


def _text(text: str) -> bytes:
    return struct.pack("<%di" % (len(text) + 1), *[ord(c) for c in text], 0)


def write_plt(path, variables, columns, zones, *, title="Tecplot output", filetype=0,
              time=0.0, strand=0) -> None:
    """Write a PLT file.

    Arguments:
        path: the file to write.
        variables: variable names, the three coordinates first.
        columns: one array per variable, all of the same length (the nodes).
        zones: list of ``(name, ztype, connectivity)``. ``ztype`` is Tecplot's code
            (2 triangle, 3 quadrilateral, 4 tetrahedron, 5 brick); connectivity is
            ``(n_elements, nodes per element)``, 0-based, into the node arrays. The first
            zone stores the variables; the others share them.
        title, filetype: header fields.
        time: solution time written to every zone.
        strand: strand id, one for every zone or a list with one per zone.
    """
    nvar = len(variables)
    columns = [np.asarray(c, dtype="<f4") for c in columns]
    if len(columns) != nvar or len({len(c) for c in columns}) != 1:
        raise ValueError("columns need one array per variable, all of one length")
    npts = len(columns[0])
    zones = [(name, int(ztype), np.asarray(conn, dtype="<i4")) for name, ztype, conn in zones]
    for name, ztype, conn in zones:
        if conn.ndim != 2 or conn.shape[1] != NPE[ztype]:
            raise ValueError(f"zone {name!r}: type {ztype} needs {NPE[ztype]} nodes per element")
        if conn.size and (conn.min() < 0 or conn.max() >= npts):
            raise ValueError(f"zone {name!r}: connectivity points outside the {npts} nodes")
    strands = [strand] * len(zones) if isinstance(strand, int) else list(strand)
    if len(strands) != len(zones):
        raise ValueError("strand needs one id per zone")
    with open(path, "wb") as f:
        f.write(b"#!TDV112" + struct.pack("<ii", 1, filetype) + _text(title))
        f.write(struct.pack("<i", nvar) + b"".join(_text(v) for v in variables))
        for (name, ztype, conn), zone_strand in zip(zones, strands):
            f.write(struct.pack("<f", 299.0) + _text(name))
            f.write(struct.pack("<iidii", -1, zone_strand, time, -1, ztype))
            f.write(struct.pack("<iii", 0, 0, 0))        # var location, face neighbours
            f.write(struct.pack("<ii", npts, len(conn)))
            f.write(struct.pack("<iiii", 0, 0, 0, 0))    # cell dims, no auxiliary data
        f.write(struct.pack("<f", 357.0))
        for i, (name, ztype, conn) in enumerate(zones):
            f.write(struct.pack("<f", 299.0) + struct.pack("<%di" % nvar, *[1] * nvar))
            if i == 0:                                    # stores every variable
                f.write(struct.pack("<iii", 0, 0, -1))   # no passive, no shared, own conn
                for c in columns:
                    lo, hi = (float(c.min()), float(c.max())) if npts else (0.0, 0.0)
                    f.write(struct.pack("<dd", lo, hi))
                for c in columns:
                    f.write(c.tobytes())
            else:                                         # shares zone 0's arrays
                f.write(struct.pack("<ii", 0, 1) + struct.pack("<%di" % nvar, *[0] * nvar))
                f.write(struct.pack("<i", -1))
            f.write(conn.tobytes())
