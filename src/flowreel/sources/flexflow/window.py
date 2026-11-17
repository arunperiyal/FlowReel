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


def cache_key(path, zone: str, box: Box, nen: int | None) -> str:
    """The key of a window: the reference file (path, size and modification time, so a
    rewritten file chooses again), the zone, ``nen`` and the box."""
    path = Path(path).resolve()
    stat = path.stat()
    parts = {"v": VERSION, "file": str(path), "size": stat.st_size, "mtime": stat.st_mtime_ns,
             "zone": zone, "nen": nen, "lo": list(box.lo), "hi": list(box.hi)}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:32]


def load(folder: Path, key: str, box: Box) -> Window | None:
    """The window stored under ``key``, or ``None``."""
    try:
        with np.load(Path(folder) / f"{key}.npz") as data:
            return Window(box, data["nodes"], data["cells"])
    except (FileNotFoundError, OSError, KeyError, ValueError):
        return None


def save(folder: Path, key: str, window: Window) -> None:
    """Store ``window`` under ``key`` (written to a temporary name, then renamed, so a
    reader never sees half a file). A folder that cannot be written is skipped."""
    try:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f"{key}.{os.getpid()}.part.npz"
        np.savez(tmp, nodes=window.nodes, cells=window.cells)
        os.replace(tmp, folder / f"{key}.npz")
    except OSError:
        pass
