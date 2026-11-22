"""A FlowReel project: a folder with ``flowreel.yml`` (plan Section 3).

``flowreel.yml`` holds what belongs to the project rather than to one shot. So far that
is ``bodies:`` (:mod:`flowreel.project.bodies`); paths, defaults and ``scales:`` come
with the phases that use them. A shot finds its project by looking for
``flowreel.yml`` in its own folder and then in each folder above it; where the
project's other files and its output go is :mod:`flowreel.project.paths`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from flowreel.project.bodies import Body, End, Series, parse_bodies
from flowreel.project.paths import PROJECT_FILE, find_root
from flowreel.scene.errors import Checker

KEYS = ("bodies",)

__all__ = ["PROJECT_FILE", "Project", "Body", "End", "Series", "load_project", "find_project",
           "project_for"]


@dataclass(frozen=True)
class Project:
    """A loaded ``flowreel.yml``: its ``file`` (``None`` when built in code), ``folder``
    and the declared ``bodies`` by name."""

    file: Path | None = None
    bodies: dict = field(default_factory=dict)

    @property
    def folder(self) -> Path | None:
        """The project folder (where relative paths in ``flowreel.yml`` start)."""
        return None if self.file is None else self.file.parent


def load_project(path: str | Path) -> Project:
    """Read and check ``flowreel.yml`` at ``path`` (a file, or a folder holding one)."""
    path = Path(path)
    if path.is_dir():
        path = path / PROJECT_FILE
    check = Checker(path)
    from flowreel.yamlfile import read_yaml
    data = read_yaml(path)
    data = check.mapping({} if data is None else data, KEYS)
    path = path.resolve()
    return Project(path, parse_bodies(data.get("bodies"), check.at("bodies"), path.parent))


def find_project(start: str | Path) -> Path | None:
    """The ``flowreel.yml`` in ``start`` (a folder, or a file's folder) or the nearest
    folder above it; ``None`` when there is none."""
    root = find_root(start)
    return None if root is None else root / PROJECT_FILE


def project_for(shot_file: str | Path | None) -> Project | None:
    """The project of a shot file, loaded; ``None`` without a file or a project."""
    if not shot_file:
        return None
    found = find_project(shot_file)
    return None if found is None else load_project(found)

