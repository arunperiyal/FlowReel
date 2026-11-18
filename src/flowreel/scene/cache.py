"""The surface cache of frozen shots (plan Sections 7.5 and 11).

A frozen shot shows one step in every frame, so its surfaces are the same in every frame
unless a layer changes the options that make them (a level track). The first frame
contours and stores each surface; later frames, each in its own process, read it back
and never load the flow. Surfaces are files because frames are drawn in separate
processes.

Key: the source, step, crop, the layer's surface options (field, level, ...) and the
code version. Files are ``<folder>/<key>.vtp`` (``.vtu`` for a volume mesh).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from flowreel.scene.keys import code_version, digest


class SurfaceCache:
    """Meshes stored under content keys in ``folder``.

    ``source`` is the shot's source as keys take it (the adapter, its resolved options
    and, in a project, the declared bodies), added to every key.
    :meth:`get` returns the stored mesh or builds, stores and returns it. ``hits`` and
    ``misses`` count what happened in this process.
    """

    def __init__(self, folder: str | Path, source=()):
        self.folder = Path(folder)
        self.source = list(source)
        self.hits = self.misses = 0

    def key(self, parts: dict) -> str:
        """The file stem for ``parts`` (with source and code added)."""
        return digest({**parts, "source": self.source, "code": code_version()})

    def get(self, parts: dict, build: Callable):
        """The mesh for ``parts``: read from the folder, or ``build()`` and stored."""
        import pyvista as pv
        stem = self.key(parts)
        for ext in (".vtp", ".vtu"):
            path = self.folder / (stem + ext)
            if path.exists():
                self.hits += 1
                return pv.read(path)
        self.misses += 1
        mesh = build()
        self.folder.mkdir(parents=True, exist_ok=True)
        ext = ".vtp" if isinstance(mesh, pv.PolyData) else ".vtu"
        tmp = self.folder / f"{stem}.{os.getpid()}.part{ext}"
        mesh.save(tmp)
        os.replace(tmp, self.folder / (stem + ext))   # readers never see half a file
        return mesh
