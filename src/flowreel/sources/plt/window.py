"""Windowed reading of a PLT file: the nodes and cells of a box (plan Section 17).

A PLT file stores each variable as one block of every node's values, so a window of a
long case is read without loading the zone: the coordinates and connectivity are read
once, in chunks, to choose the window's cells and the nodes they use (the
:class:`Window`), and each step then reads only those nodes of the asked variables
through a memory map. Memory and time per step follow the window, not the domain.

The connectivity does not change between steps, so a window chosen at one step serves
every step; its box is the crop grown by a margin for the body's motion. Each step's
cells are then cut to the crop exactly as a whole read would cut them.

A window that travels along a long body has a new box every frame, so choosing by a scan
of the whole zone each time would cost as much as reading it. The :class:`SpanIndex`,
built once per case and kept on disk, holds the cells sorted by their least coordinate
along the span: a box's cells are then a binary search away, and only they are read.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flowreel.box import Box

CHUNK = 4_000_000          # nodes or elements per chunk while choosing the window
VERSION = 1                # of the cached index's layout


def default_cache() -> Path:
    """Where window indexes are kept: ``$XDG_CACHE_HOME/flowreel/windows`` (default
    ``~/.cache/flowreel/windows``), outside the case, which may be read-only."""
    root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(root) / "flowreel" / "windows"


@dataclass(frozen=True)
class Window:
    """The part of a zone in ``box``: ``nodes`` (sorted node numbers in the file) and
    ``cells`` (connectivity numbered into ``nodes``)."""

    box: Box
    nodes: np.ndarray
    cells: np.ndarray

    @property
    def nbytes(self) -> int:
        """Memory of the index itself."""
        return int(self.nodes.nbytes + self.cells.nbytes)


@dataclass(frozen=True)
class SpanIndex:
    """The cells of a zone sorted along ``axis`` (0, 1, 2: its longest extent):
    ``order`` (cell numbers) and ``lo`` (each one's least coordinate on that axis,
    ascending)."""

    axis: int
    order: np.ndarray
    lo: np.ndarray

    def candidates(self, box: Box) -> np.ndarray:
        """Cells that may lie in ``box``: those starting inside it along the axis, in
        ascending cell number (for page locality)."""
        k = self.axis
        a = np.searchsorted(self.lo, box.lo[k], side="left")
        b = np.searchsorted(self.lo, box.hi[k], side="right")
        return np.sort(self.order[a:b])


def build_span(plt, zi: int, nen: int | None = None, chunk: int = CHUNK) -> SpanIndex:
    """The :class:`SpanIndex` of zone ``zi``, its axis the longest side of the zone's
    bounds (from the file header), read in chunks."""
    mm = plt.minmax(zi)
    sides = [mm[v][1] - mm[v][0] for v in plt.vars[:3]]
    k = int(np.argmax(sides))
    along = plt.map_variable(zi, plt.vars[k])
    conn = plt.map_connectivity(zi, nen)
    npts = len(along)
    lows = np.empty(len(conn), dtype=np.float32)
    for start in range(0, len(conn), chunk):
        part = np.asarray(conn[start:start + chunk], dtype=np.int64)
        bad = ~((part >= 0) & (part < npts)).all(axis=1)
        part[bad] = 0
        lows[start:start + len(part)] = np.asarray(along[part.ravel()]).reshape(part.shape).min(axis=1)
        lows[start:start + len(part)][bad] = np.inf                   # never chosen
    order = np.argsort(lows, kind="stable")
    return SpanIndex(k, order, lows[order])


def choose(plt, zi: int, box: Box, nen: int | None = None, chunk: int = CHUNK,
           span: SpanIndex | None = None) -> Window:
    """The cells of zone ``zi`` of ``plt`` (a :class:`~flowreel.sources.plt.reader.PltFile`)
    with every node in ``box``, and their nodes. With ``span`` only the cells it names
    for the box are read; without, the coordinates and the connectivity are read in
    chunks of ``chunk``, never whole."""
    if span is not None:
        return _choose_from(plt, zi, box, nen, span)
    coords = [plt.map_variable(zi, v) for v in plt.vars[:3]]
    npts = len(coords[0])
    inside = np.zeros(npts, dtype=bool)
    for start in range(0, npts, chunk):
        part = np.column_stack([c[start:start + chunk] for c in coords]).astype(np.float64)
        inside[start:start + chunk] = box.contains(part)
    conn = plt.map_connectivity(zi, nen)
    if conn is None:
        raise ValueError(f"zone {plt.zones[zi]['name']!r} of {plt.path} has no connectivity "
                         "of its own")
    kept = []
    for start in range(0, len(conn), chunk):
        part = np.asarray(conn[start:start + chunk], dtype=np.int64)
        valid = ((part >= 0) & (part < npts)).all(axis=1)
        part = part[valid]
        kept.append(part[inside[part].all(axis=1)])
    cells = np.concatenate(kept) if kept else np.empty((0, conn.shape[1]), np.int64)
    nodes = np.unique(cells)
    return Window(box, nodes, np.searchsorted(nodes, cells))


def _choose_from(plt, zi: int, box: Box, nen, span: SpanIndex) -> Window:
    cand = span.candidates(box)
    conn = plt.map_connectivity(zi, nen)
    coords = [plt.map_variable(zi, v) for v in plt.vars[:3]]
    cells = np.asarray(conn[cand], dtype=np.int64) if len(cand) else \
        np.empty((0, conn.shape[1]), np.int64)
    nodes = np.unique(cells)
    points = np.column_stack([np.asarray(c[nodes], dtype=np.float64) for c in coords]) \
        if len(nodes) else np.empty((0, 3))
    inside = box.contains(points)
    local = np.searchsorted(nodes, cells)
    cells = cells[inside[local].all(axis=1)] if len(cells) else cells
    kept = np.unique(cells)
    return Window(box, kept, np.searchsorted(kept, cells))


def span_key(path, zone: str, nen: int | None) -> str:
    """The key of a span index: the file (path, size, modification time), zone, ``nen``."""
    path = Path(path).resolve()
    stat = path.stat()
    parts = {"v": VERSION, "kind": "span", "file": str(path), "size": stat.st_size,
             "mtime": stat.st_mtime_ns, "zone": zone, "nen": nen}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:32]


def load_span(folder: Path, key: str) -> SpanIndex | None:
    """The span index stored under ``key``, or ``None``."""
    try:
        with np.load(Path(folder) / f"{key}.npz") as data:
            return SpanIndex(int(data["axis"]), data["order"], data["lo"])
    except (FileNotFoundError, OSError, KeyError, ValueError):
        return None


def save_span(folder: Path, key: str, span: SpanIndex) -> None:
    """Store ``span`` under ``key`` (through a temporary name); an unwritable folder is
    skipped."""
    try:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f"{key}.{os.getpid()}.part.npz"
        np.savez(tmp, axis=span.axis, order=span.order, lo=span.lo)
        os.replace(tmp, folder / f"{key}.npz")
    except OSError:
        pass


def read(plt, zi: int, window: Window, names: list[str]) -> dict:
    """The window's values of ``names`` (variables of the file), each a float32 array
    in the order of ``window.nodes``; ``None`` for a passive variable."""
    out = {}
    for name in names:
        mapped = plt.map_variable(zi, name)
        out[name] = None if mapped is None else np.asarray(mapped[window.nodes], dtype="<f4")
    return out

