"""Where a project's files are and where its output goes (plan Section 23, question 6).

A project is a folder with ``flowreel.yml``. Commands find it by walking up from the
file they act on (or the current folder), so they work the same from any folder inside
it. What a person writes stays visible at the root and in its folders
(:data:`FOLDERS`); what FlowReel makes goes under the root too, wherever the command was
run from: frames in ``frames/``, finished clips in ``clips/`` (:data:`OUTPUTS`), and
machine state, which nobody edits, in the hidden ``.flowreel/`` (:data:`STATE`): the
surface cache, measured frame costs and the record of Slurm jobs. One ``cameras.yml`` at
the root serves every shot and caption.

The commands stop outside a project (:func:`require_root`); the library does not, and
keeps its files beside the file it was given, as before projects had rules.
"""
from __future__ import annotations

from pathlib import Path

from flowreel.scene.errors import ConfigError

PROJECT_FILE = "flowreel.yml"
CAMERAS_FILE = "cameras.yml"
FILM_FILE = "film.yml"
#: Folders ``project init`` makes for what is written by hand (and ``data/`` for links).
FOLDERS = ("shots", "text", "cards", "assets", "data")
#: Generated output, under the root.
OUTPUTS = ("frames", "clips")
#: Machine state: caches, measured timings, job records.
STATE = ".flowreel"
#: What the ``.gitignore`` of a project leaves out: everything generated, and the data.
IGNORED = ("frames/", "clips/", ".flowreel/", "data/")


class NotInProject(ConfigError):
    """A command was run outside a project."""


def find_root(start: str | Path | None = None) -> Path | None:
    """The project folder holding ``start`` (a folder, or a file's folder; default the
    current folder): the nearest folder, ``start``'s own or one above, with a
    ``flowreel.yml``. ``None`` when there is none."""
    start = Path.cwd() if start is None else Path(start).expanduser()
    start = start.resolve()
    folder = start if start.is_dir() else start.parent
    for d in (folder, *folder.parents):
        if (d / PROJECT_FILE).is_file():
            return d
    return None


def require_root(start: str | Path | None = None) -> Path:
    """:func:`find_root`, or :class:`NotInProject` saying how to make a project."""
    root = find_root(start)
    if root is None:
        where = Path.cwd() if start is None else Path(start).expanduser().resolve()
        raise NotInProject(
            f"{where} is not in a FlowReel project (no {PROJECT_FILE} there or in any "
            f"folder above). Make one with 'flowreel project init' in the project's "
            f"folder (for example: flowreel project init vtk:run/flow.pvd), or cd into "
            f"one. Reference: docs/project.md")
    return root


def output(start: str | Path | None, kind: str) -> Path:
    """The folder of generated ``kind`` (``frames``, ``clips``) for ``start``:
    ``<root>/<kind>`` in a project, else ``<start's folder>/<kind>``."""
    root = find_root(start)
    if root is not None:
        return root / kind
    base = Path.cwd() if start is None else Path(start).expanduser().resolve()
    return (base if base.is_dir() else base.parent) / kind


def state(start: str | Path | None) -> Path | None:
    """The ``.flowreel/`` folder of the project holding ``start``; ``None`` outside one."""
    root = find_root(start)
    return None if root is None else root / STATE


def cameras_file(start: str | Path) -> Path:
    """The ``cameras.yml`` for a shot or caption file at ``start``: at the project root,
    or beside the file outside a project. In a project, a ``cameras.yml`` left beside a
    file below the root is an error that says to move it (one file serves every shot)."""
    start = Path(start).expanduser().resolve()
    folder = start if start.is_dir() else start.parent
    root = find_root(folder)
    if root is None:
        return folder / CAMERAS_FILE
    stray = folder / CAMERAS_FILE
    if folder != root and stray.is_file():
        raise ConfigError(
            f"{stray}: a project has one {CAMERAS_FILE}, at its root; move this one to "
            f"{root / CAMERAS_FILE} (merge their views and tracks if both exist)")
    return root / CAMERAS_FILE
