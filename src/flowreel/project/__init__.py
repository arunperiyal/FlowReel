"""A FlowReel project: a folder with ``flowreel.yml`` (plan Section 3).

``flowreel.yml`` holds what belongs to the project rather than to one shot. So far that
is ``defaults:`` (:data:`DEFAULT_KEYS`) and ``tags:``, the project's tags; each case's
bodies, units and series are in its tag's ``data/<tag>/domain.yml``
(:mod:`flowreel.project.domain`). ``bodies:`` and ``reference:`` (:data:`REFERENCE_KEYS`),
the layout before tags, are read until the tutorials and examples move to tags
(Phase 10), then removed. A shot finds its project by looking for
``flowreel.yml`` in its own folder and then in each folder above it; where the
project's other files and its output go is :mod:`flowreel.project.paths`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from flowreel.project.bodies import Body, End, Series, parse_bodies
from flowreel.project.paths import PROJECT_FILE, find_root
from flowreel.scene.errors import Checker

KEYS = ("bodies", "reference", "defaults", "tags")
#: Keys of ``defaults:``: what every command of the project starts from.
DEFAULT_KEYS = ("backend", "style")
#: The keys of ``reference:``: ``rho`` (density) and ``u_inf`` (free-stream speed), the
#: parameters of the pressure and skin-friction coefficients; ``length``, the length a
#: shot's axes divide by with ``unit: diameters`` when they name no body.
REFERENCE_KEYS = ("rho", "u_inf", "length")

__all__ = ["PROJECT_FILE", "Project", "Body", "End", "Series", "load_project", "find_project",
           "project_for"]


@dataclass(frozen=True)
class Project:
    """A loaded ``flowreel.yml``: its ``file`` (``None`` when built in code), ``folder``,
    the declared ``bodies`` by name and the ``reference`` values given (a subset of
    :data:`REFERENCE_KEYS`, each a positive number)."""

    file: Path | None = None
    bodies: dict = field(default_factory=dict)
    reference: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    tag_names: tuple = ()

    @property
    def tags(self) -> dict:
        """The project's tags (``data/<tag>/domain.yml``), by name
        (:func:`flowreel.project.domain.domains`); none without a file."""
        from flowreel.project.domain import domains
        return {} if self.folder is None else domains(self.folder)

    @property
    def folder(self) -> Path | None:
        """The project folder (where relative paths in ``flowreel.yml`` start)."""
        return None if self.file is None else self.file.parent

    def named_bodies(self) -> dict:
        """Every body a panel of the project may name: ``flowreel.yml``'s by their names,
        each tag's as ``tag.body``, and a tag's body by its own name too when no other
        tag and no ``flowreel.yml`` body has that name."""
        out = dict(self.bodies)
        owners: dict[str, list[str]] = {}
        for tag, domain in self.tags.items():
            for name, body in domain.bodies.items():
                out[f"{tag}.{name}"] = body
                owners.setdefault(name, []).append(f"{tag}.{name}")
        for name, names in owners.items():
            if name not in out and len(names) == 1:
                out[name] = out[names[0]]
        return out

    def body(self, name: str):
        """The :class:`~flowreel.project.bodies.Body` a panel names (see
        :meth:`named_bodies`). Raises ``LookupError`` saying what to write instead."""
        named = self.named_bodies()
        if name in named:
            return named[name]
        same = [n for n in named if n.endswith("." + name)]
        if same:
            raise LookupError(f"several tags have a body {name!r}: name one as "
                              f"{' or '.join(same)}")
        raise LookupError(f"no body {name!r} in {self.file} or its tags (bodies: "
                          f"{', '.join(named) or 'none'})")

    def owners(self, series: str) -> list[str]:
        """The names (as :meth:`named_bodies` gives them, each body once, ``tag.body``
        for a tag's) of the bodies declaring a series called ``series``."""
        seen, out = set(), []
        for name, body in self.named_bodies().items():
            if series in body.series and id(body) not in seen:
                seen.add(id(body))
                out.append(name)
        return out


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
    return Project(path, parse_bodies(data.get("bodies"), check.at("bodies"), path.parent),
                   parse_reference(data.get("reference"), check.at("reference")),
                   parse_defaults(data.get("defaults"), check.at("defaults")),
                   parse_tag_names(data.get("tags"), check.at("tags")))


def parse_defaults(value, check: Checker) -> dict:
    """``defaults:`` checked: ``backend`` (one of the off-screen back ends) and ``style``
    (a mapping, the film's style)."""
    if value is None:
        return {}
    from flowreel.scene.backend import BACKENDS
    out = dict(check.mapping(value, DEFAULT_KEYS))
    if "backend" in out:
        check.at("backend").choice(out["backend"], BACKENDS)
    if "style" in out:
        check.at("style").mapping(out["style"], tuple(out["style"] or {}))
    return out


def parse_tag_names(value, check: Checker) -> tuple:
    """``tags:`` checked: a list of tag names (each a folder under ``data/``)."""
    if value is None:
        return ()
    from flowreel.project.domain import check_tag
    if not isinstance(value, list):
        raise check.error(f"expected a list of tag names, got {value!r}")
    return tuple(check_tag(v, check.at(k)) for k, v in enumerate(value))


def parse_reference(value, check: Checker) -> dict:
    """``reference:`` checked: a mapping of :data:`REFERENCE_KEYS`, each positive."""
    if value is None:
        return {}
    out = {}
    for key, number in check.mapping(value, REFERENCE_KEYS).items():
        out[key] = check.at(key).number(number)
        if out[key] <= 0:
            raise check.at(key).error(f"must be positive, got {out[key]:g}")
    return out


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

