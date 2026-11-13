"""Cut a small test file out of FlexFlow PLT output.

Usage: python tools/cut_plt.py OUT_DIR --box X0 Y0 Z0 X1 Y1 Z1 FILE [FILE ...]

Keeps the volume cells with every node inside the box *in the first file*, and the body
quads whose nodes all survive; the same cells are then cut from the other files, so the
mesh topology is the same in every step even though the mesh moves. The output has the
layout FlexFlow writes (TDV112, block data, float32, a body zone sharing the volume
zone's arrays), with the title, strand and solution time of the original.

This is how tests/data/flexflow_case/ was made; it is not part of the package.
"""
import argparse
import struct
from pathlib import Path

import numpy as np

from flowreel.sources.flexflow.plt import PltFile


def _s(text):
    return struct.pack("<%di" % (len(text) + 1), *[ord(c) for c in text], 0)


def write(path, src, vol, surf, cols, vconn, sconn):
    """Write a two-zone file: volume zone ``vol`` and body zone ``surf`` (dicts of the
    source's zone records), ``cols`` one float32 array per variable."""
    nvar, npts = len(src.vars), len(cols[0])
    with open(path, "wb") as f:
        f.write(b"#!TDV112" + struct.pack("<ii", 1, src.filetype) + _s(src.title))
        f.write(struct.pack("<i", nvar) + b"".join(_s(v) for v in src.vars))
        for zone, conn in ((vol, vconn), (surf, sconn)):
            f.write(struct.pack("<f", 299.0) + _s(zone["name"]))
            f.write(struct.pack("<iidii", -1, zone["strand"], zone["time"], -1, zone["ztype"]))
            f.write(struct.pack("<iii", 0, 0, 0))        # var location, face neighbours
            f.write(struct.pack("<ii", npts, len(conn)))
            f.write(struct.pack("<iiii", 0, 0, 0, 0))    # cell dims, no auxiliary data
        f.write(struct.pack("<f", 357.0))
        # volume zone: stores everything
        f.write(struct.pack("<f", 299.0) + struct.pack("<%di" % nvar, *[1] * nvar))
        f.write(struct.pack("<iii", 0, 0, -1))           # no passive, no shared, own conn
        for c in cols:
            f.write(struct.pack("<dd", float(c.min()), float(c.max())))
        for c in cols:
            f.write(c.astype("<f4").tobytes())
        f.write(vconn.astype("<i4").tobytes())
        # body zone: every variable shared from zone 0, its own connectivity
        f.write(struct.pack("<f", 299.0) + struct.pack("<%di" % nvar, *[1] * nvar))
        f.write(struct.pack("<ii", 0, 1) + struct.pack("<%di" % nvar, *[0] * nvar))
        f.write(struct.pack("<i", -1))
        f.write(sconn.astype("<i4").tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--box", nargs=6, type=float, required=True)
    parser.add_argument("--volume", default="FIELD")
    parser.add_argument("--body", default="cyl")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lo, hi = np.array(args.box[:3]), np.array(args.box[3:])
    keep_v = keep_s = used = None
    for path in args.files:
        with PltFile(path) as src:
            vi, si = src.zone_index(args.volume), src.zone_index(args.body)
            vconn, sconn = src.load_connectivity(vi), src.load_connectivity(si)
            cols = [src.read_variable(vi, name) for name in src.vars]
            if keep_v is None:
                pts = np.column_stack(cols[:3])
                inside = np.all((pts >= lo) & (pts <= hi), axis=1)
                keep_v = inside[vconn].all(axis=1)
                used = np.unique(vconn[keep_v])
                in_cut = np.zeros(len(pts), bool)
                in_cut[used] = True
                keep_s = in_cut[sconn].all(axis=1)
            remap = np.full(len(cols[0]), -1, np.int64)
            remap[used] = np.arange(len(used))
            out = args.out / path.name
            write(out, src, src.zones[vi], src.zones[si], [c[used] for c in cols],
                  remap[vconn[keep_v]], remap[sconn[keep_s]])
            print(f"{out}: {len(used)} nodes, {keep_v.sum()} cells, {keep_s.sum()} body quads, "
                  f"{out.stat().st_size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
