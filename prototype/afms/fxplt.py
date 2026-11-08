"""
fxplt.py  --  Reader for FlexFlow Tecplot binary (.plt, "#!TDV112") output.

FlexFlow's Tecplot binary writer is *mostly* standard TDV112 but trips up
ParaView/Tecplot's own readers (they fall back to the surface zone with no
data arrays). This module parses the file directly with numpy, exposes the
zone/variable layout, loads a chosen zone's nodal data + connectivity, and
*detects/recovers truncated files* (a run killed mid-write leaves a partial
connectivity block).

Layout assumptions (verified against the cylinder_12 cases):
  - All nodal variables, block (var-major) ordering, float32.
  - Element connectivity is 0-based int32, nodes-per-element from zone type.

Typical use:
    from src.plt.fxplt import PltFile
    p = PltFile("riser.5000.plt")
    print(p.summary())
    zi = p.first_volume_zone()
    pts, conn, pdata, info = p.load_zone(zi)   # info['truncated'], etc.
"""
import struct
import numpy as np

EOH_MARKER = 357.0
ZONE_MARKER = 299.0
FMT_SIZE = {1: 4, 2: 8, 3: 4, 4: 2, 5: 1, 6: 1}      # Tecplot data-format codes
FMT_NP = {1: "<f4", 2: "<f8", 3: "<i4", 4: "<i2", 5: "<i1"}
# nodes-per-element by Tecplot zone-type code:
#   1=FELINESEG(2) 2=FETRIANGLE(3) 3=FEQUADRILATERAL(4)
#   4=FETETRAHEDRON(4) 5=FEBRICK(8)
# WARNING: the zone type cannot always be trusted -- e.g. an 8-node hex mesh
# written with simflow.config nen=4 comes out labelled ztype 4 (tet) carrying
# only 4 of 8 nodes. Use load_zone(zi, nen=...) to force the true
# nodes-per-element when the header is wrong.
NPE = {1: 2, 2: 3, 3: 4, 4: 4, 5: 8}
ZTYPE_VTK = {2: "triangle", 3: "quad", 4: "tetra", 5: "hexahedron"}
VOLUME_ZTYPES = (4, 5)
SURFACE_ZTYPES = (2, 3)


# ---- primitive binary readers (shared by header, preamble, and minmax parsing) --
def _i32(f):
    return struct.unpack("<i", f.read(4))[0]


def _f32(f):
    return struct.unpack("<f", f.read(4))[0]


def _f64(f):
    return struct.unpack("<d", f.read(8))[0]


def _tstr(f):
    s = []
    while True:
        c = _i32(f)
        if c == 0:
            break
        s.append(chr(c))
    return "".join(s)


class PltFile:
    def __init__(self, path):
        self.path = str(path)
        self.vars = []
        self.zones = []          # list of dicts: name, ztype, npts, nelem
        self._data_start = None  # byte offset of the data section (after EOH)
        self._layout_cache = None
        self._parse_header()

    def close(self):
        """Release the file handle kept open for the life of this instance."""
        self._f.close()

    # ---- header / zone records -------------------------------------------
    def _parse_header(self):
        f = open(self.path, "rb")
        self._f = f

        magic = f.read(8)
        if magic != b"#!TDV112":
            raise ValueError("not a TDV112 Tecplot binary file: %r" % magic)
        assert _i32(f) == 1, "byte-order check failed"
        self.filetype = _i32(f)
        self.title = _tstr(f)
        nvar = _i32(f)
        self.vars = [_tstr(f) for _ in range(nvar)]

        while True:
            m = _f32(f)
            if abs(m - EOH_MARKER) < 1e-3:
                break
            assert abs(m - ZONE_MARKER) < 1e-3, ("bad zone marker", m)
            name = _tstr(f)
            _i32(f)                     # parent zone
            _i32(f)                     # strand id
            _f64(f)                     # solution time
            _i32(f)                     # default zone color
            ztype = _i32(f)
            if _i32(f) == 1:            # var location specified
                for _ in range(nvar):
                    _i32(f)
            _i32(f)                     # raw face neighbours
            if _i32(f) > 0:              # user-defined face neighbour conns
                _i32(f)
            npts = _i32(f)
            nelem = _i32(f)
            _i32(f); _i32(f); _i32(f)   # i/j/k cell dims (reserved)
            while _i32(f) == 1:          # auxiliary name/value pairs
                _tstr(f); _i32(f); _tstr(f)
            self.zones.append(dict(name=name, ztype=ztype, npts=npts, nelem=nelem))
        self._data_start = f.tell()

    # ---- helpers ----------------------------------------------------------
    def first_volume_zone(self):
        for i, z in enumerate(self.zones):
            if z["ztype"] in VOLUME_ZTYPES:
                return i
        return 0

    def summary(self):
        import os
        lines = ["file: %s (%d bytes)" % (self.path, os.path.getsize(self.path))]
        lines.append("vars (%d): %s" % (len(self.vars), ", ".join(self.vars)))
        for i, z in enumerate(self.zones):
            lines.append("  zone %d '%s'  ztype=%d  npts=%d  nelem=%d"
                         % (i, z["name"], z["ztype"], z["npts"], z["nelem"]))
        return "\n".join(lines)

    def _read_data_preamble(self, f, nvar, keep_minmax=False):
        """Read one zone's data-section preamble.

        Returns (fmts, present_mask, shareconn, shared, minmax) where shared[v] is
        the zone variable v is borrowed from (-1 = this zone stores it) and
        minmax[v] is that variable's (min, max) doubles when keep_minmax is True
        (None otherwise, and always None where present_mask[v] is False). Tecplot
        lets a zone carry no data of its own and point every variable at another
        zone -- how a surface zone rides along on the volume zone's node array.
        """
        m = _f32(f)
        assert abs(m - ZONE_MARKER) < 1e-3, ("bad data marker", m)
        fmts = [_i32(f) for _ in range(nvar)]
        passive = [0] * nvar
        if _i32(f) == 1:
            passive = [_i32(f) for _ in range(nvar)]
        shared = [-1] * nvar
        if _i32(f) == 1:
            shared = [_i32(f) for _ in range(nvar)]
        shareconn = _i32(f)
        present = [(passive[v] == 0 and shared[v] == -1) for v in range(nvar)]
        minmax = [None] * nvar
        for v in range(nvar):
            if present[v]:
                if keep_minmax:
                    minmax[v] = (_f64(f), _f64(f))
                else:
                    f.read(16)
        return fmts, present, shareconn, shared, minmax

    # ---- data-section map -------------------------------------------------
    def _layout(self):
        """Byte offset of every zone's variable blocks and connectivity.

        One cheap pass over the data section (preambles only, bulk data seeked
        past), so a variable can afterwards be read straight from whichever zone
        actually stores it.
        """
        if self._layout_cache is not None:
            return self._layout_cache
        nvar = len(self.vars)
        f = self._f
        f.seek(self._data_start)
        layout = []
        for z in self.zones:
            fmts, present, shareconn, shared, _ = self._read_data_preamble(f, nvar)
            entry = dict(fmts=fmts, present=present, shared=shared,
                         shareconn=shareconn, var_offset={}, conn_offset=None)
            for v in range(nvar):
                if present[v]:
                    entry["var_offset"][v] = f.tell()
                    f.seek(z["npts"] * FMT_SIZE[fmts[v]], 1)
            if shareconn == -1 and z["ztype"] in NPE:
                entry["conn_offset"] = f.tell()
                f.seek(z["nelem"] * NPE[z["ztype"]] * 4, 1)
            layout.append(entry)
        self._layout_cache = layout
        return layout

    def load_connectivity(self, zi, nen=None):
        """Read one zone's connectivity alone, in the shared (parent) node indexing.

        Cheap next to load_zone -- no variable data is touched -- which is what a
        surface zone needs when its nodal values are being read from the volume
        zone anyway. Returns None if the zone borrows its connectivity too.
        """
        entry = self._layout()[zi]
        if entry["conn_offset"] is None:
            return None
        z = self.zones[zi]
        npe = nen if nen is not None else NPE.get(z["ztype"], 8)
        f = self._f
        f.seek(entry["conn_offset"])
        raw = np.fromfile(f, dtype="<i4", count=z["nelem"] * npe)
        nelem = raw.size // npe
        conn = raw[:nelem * npe].reshape(nelem, npe)
        good = ((conn >= 0) & (conn < z["npts"])).all(axis=1)
        nvalid = int(np.argmin(good)) if not good.all() else nelem
        return conn[:nvalid].astype(np.int64)

    def variable_owner(self, zi, v, _depth=0):
        """Zone that actually stores variable `v` for zone `zi`, or None if passive."""
        entry = self._layout()[zi]
        if entry["present"][v]:
            return zi
        src = entry["shared"][v]
        if src is None or not (0 <= src < len(self.zones)) or _depth > len(self.zones):
            return None
        return self.variable_owner(src, v, _depth + 1)

    def shared_from(self, zi):
        """Zones this one borrows variables from (empty if it stores its own)."""
        entry = self._layout()[zi]
        return sorted({entry["shared"][v] for v in range(len(self.vars))
                       if not entry["present"][v] and entry["shared"][v] is not None
                       and entry["shared"][v] >= 0})

    def minmax(self, zi=0):
        """Return {var: (min, max) or None} for a zone, read from the header (no bulk load).

        A shared variable reports None on purpose: the owning zone's range covers
        the owner's whole node array, which is wider than the subset a surface zone
        actually occupies. Do not "fix" this by following the share -- callers use
        None to mean "compute it from the loaded points instead".
        """
        nvar = len(self.vars)
        f = self._f
        f.seek(self._data_start)

        # skip the data of any zones before the target
        for j in range(zi):
            zt = self.zones[j]
            fmts, present, shareconn, _, _ = self._read_data_preamble(f, nvar)
            for v in range(nvar):
                if present[v]:
                    f.seek(zt["npts"] * FMT_SIZE[fmts[v]], 1)
            if shareconn == -1 and zt["ztype"] in NPE:
                f.seek(zt["nelem"] * NPE[zt["ztype"]] * 4, 1)

        _, present, _, _, minmax = self._read_data_preamble(f, nvar, keep_minmax=True)
        return {self.vars[v]: minmax[v] if present[v] else None for v in range(nvar)}

    # ---- main loader ------------------------------------------------------
    def load_zone(self, zi, nen=None):
        """Load nodal data + connectivity for zone `zi`.

        nen : override nodes-per-element (default: from the zone type). Use this
              when the writer mislabels the zone (e.g. an 8-node hex mesh emitted
              as ztype 4 / 4-node because of simflow.config nen=4).

        Returns (points[N,3] f32, conn[M,npe] int64, point_data{name:array},
                 info{truncated, nhex_file, nhex_valid, ...}).
        Variables the zone does not store itself are read from the zone that does,
        so a surface zone sharing the volume zone's arrays loads normally; such a
        zone is then compacted to the nodes its own elements actually use, and its
        connectivity renumbered to match. Detects truncation and clips connectivity
        to the leading all-valid prefix.
        """
        nvar = len(self.vars)
        layout = self._layout()
        entry = layout[zi]
        f = self._f

        z = self.zones[zi]
        npts, nelem, ztype = z["npts"], z["nelem"], z["ztype"]
        shareconn = entry["shareconn"]

        cols = {}
        for v in range(nvar):
            owner = self.variable_owner(zi, v)
            if owner is None:                       # passive: nothing stored anywhere
                cols[self.vars[v]] = None
                continue
            count = self.zones[owner]["npts"]
            f.seek(layout[owner]["var_offset"][v])
            arr = np.fromfile(f, dtype=FMT_NP[layout[owner]["fmts"][v]], count=count)
            if arr.size < count:
                raise IOError("truncated inside variable '%s' (%d/%d values)"
                              % (self.vars[v], arr.size, count))
            cols[self.vars[v]] = arr.astype("<f4", copy=False)

        npe = nen if nen is not None else NPE.get(ztype, 8)
        borrowed = self.shared_from(zi)
        info = dict(zone=zi, npts=npts, nelem=nelem, ztype=ztype, npe=npe,
                    nen_declared=NPE.get(ztype), nen_override=nen,
                    truncated=False, nhex_file=nelem, nhex_valid=nelem,
                    shared_from=borrowed)
        if shareconn == -1 and entry["conn_offset"] is not None:
            f.seek(entry["conn_offset"])
            raw = np.fromfile(f, dtype="<i4", count=nelem * npe)
            nhex_file = raw.size // npe
            conn = raw[:nhex_file * npe].reshape(nhex_file, npe)
            good = ((conn >= 0) & (conn < npts)).all(axis=1)
            nvalid = int(np.argmin(good)) if not good.all() else nhex_file
            if nhex_file < nelem or nvalid < nhex_file:
                info["truncated"] = True
            info["nhex_file"] = nhex_file
            info["nhex_valid"] = nvalid
            conn = conn[:nvalid].astype(np.int64)
        else:
            conn = None  # connectivity shared from another zone

        # Each column is already a fresh, contiguous <f4 array (from np.fromfile /
        # astype above), and column_stack always allocates fresh+contiguous too --
        # no further copying needed here.
        pts = np.column_stack([cols[self.vars[0]], cols[self.vars[1]], cols[self.vars[2]]])
        pdata = {self.vars[v]: cols[self.vars[v]]
                 for v in range(3, nvar) if cols[self.vars[v]] is not None}

        # A zone riding on another zone's arrays covers only the nodes its own
        # elements touch -- keep those, and renumber the connectivity to match.
        if borrowed and conn is not None and len(conn):
            used = np.unique(conn)
            if len(used) < len(pts):
                remap = np.full(len(pts), -1, dtype=np.int64)
                remap[used] = np.arange(len(used))
                pts = pts[used]                     # fancy indexing: fresh, contiguous
                conn = remap[conn]
                pdata = {k: v[used] for k, v in pdata.items()}
                info["npts_shared"] = npts
                info["npts"] = len(used)
                info["parent_nodes"] = used     # index back into the owning zone
        return pts, conn, pdata, info


if __name__ == "__main__":
    import sys
    p = PltFile(sys.argv[1])
    print(p.summary())
