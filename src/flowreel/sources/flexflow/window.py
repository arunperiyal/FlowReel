"""Windowed reading of a PLT file: the nodes and cells of a box (plan Section 17).

A PLT file stores each variable as one block of every node's values, so a window of a
long case is read without loading the zone: the coordinates and connectivity are read
once, in chunks, to choose the window's cells and the nodes they use (the
:class:`Window`), and each step then reads only those nodes of the asked variables
through a memory map. Memory and time per step follow the window, not the domain.

The connectivity does not change between steps, so a window chosen at one step serves
every step; its box is the crop grown by a margin for the body's motion. Each step's
cells are then cut to the crop exactly as a whole read would cut them.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flowreel.box import Box

CHUNK = 4_000_000          # nodes or elements per chunk while choosing the window


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


def choose(plt, zi: int, box: Box, nen: int | None = None, chunk: int = CHUNK) -> Window:
    """The cells of zone ``zi`` of ``plt`` (a :class:`~flowreel.sources.flexflow.plt.PltFile`)
    with every node in ``box``, and their nodes. Reads the coordinates and the
    connectivity in chunks of ``chunk``, never whole."""
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


def read(plt, zi: int, window: Window, names: list[str]) -> dict:
    """The window's values of ``names`` (variables of the file), each a float32 array
    in the order of ``window.nodes``; ``None`` for a passive variable."""
    out = {}
    for name in names:
        mapped = plt.map_variable(zi, name)
        out[name] = None if mapped is None else np.asarray(mapped[window.nodes], dtype="<f4")
    return out
