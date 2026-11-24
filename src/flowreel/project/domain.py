"""A project's data by tag: each case under ``data/<tag>/``, described by its own
``domain.yml`` (plan Section 19.10, Phase 9; Section 24, question 11).

.. code-block:: yaml

    # data/bare/domain.yml
    kind: plt                       # plt, vtk or geometry
    source: {path: plt}             # the reader's options; paths from this folder
    units: {rho: 1000.0, mu: 1.0, u_inf: 1.0, length: 1.0}
    bodies:
      cyl:
        zone: cyl
        axis: x
        diameter: 1.0
        series:
          force: {file: series/force.csv}

A **tag** is one case: its flow (``plt`` or ``vtk``, linked under the tag's folder), and
what was made from it (``series/``). Its name is letters, digits, ``-`` and ``_``: no
dots, since a body across tags is written ``tag.body``. Its ``bodies`` are declared as
a project's are (:mod:`flowreel.project.bodies`), but belong to the tag, so two tags may
both have a body on a zone called ``cyl``. Its ``units`` are the case's constants: the
parameters of the derived fields that take them (``rho``, ``mu``, ``u_inf``, ``p_inf``;
``length`` is the length lengths are shown in). A ``geometry`` tag has no data: its
``source`` names a body made in code and its parameters.

``measured:`` is what ``data import`` found (steps, zones, fields, bounds), kept for
reading; nothing reads it back.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.errors import Checker

#: The file of a tag, in its folder under ``data/``.
DOMAIN_FILE = "domain.yml"
#: The kinds of tag, each opened with the source adapter of the same name.
KINDS = ("plt", "vtk", "geometry")
KEYS = ("kind", "source", "units", "bodies", "measured")
#: The case's constants: the derived fields' parameters, and the unit of lengths shown.
UNIT_KEYS = ("rho", "mu", "u_inf", "p_inf", "length")
#: Units that are field parameters (``length`` is not).
FIELD_PARAMS = ("rho", "mu", "u_inf", "p_inf")
TAG = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class Domain:
    """A tag's ``domain.yml``: the ``tag``, its ``folder``, its ``kind``, the reader's
    ``source`` options (paths resolved from the folder), its ``units`` and ``bodies``
    (name to :class:`~flowreel.project.bodies.Body`), and ``measured``."""

    tag: str
    folder: Path
    kind: str
    source: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    bodies: dict = field(default_factory=dict)
    measured: dict = field(default_factory=dict)

    @property
    def params(self) -> dict:
        """The units that are parameters of derived fields."""
        return {k: v for k, v in self.units.items() if k in FIELD_PARAMS}


def check_tag(name, check: Checker) -> str:
    """``name`` if it is a tag's name (letters, digits, ``-`` and ``_``), else an error."""
    if not isinstance(name, str) or not TAG.match(name):
        raise check.error(f"a tag is letters, digits, '-' and '_' (no dots: a body across "
                          f"tags is written tag.body), got {name!r}")
    return name


def load_domain(folder: str | Path) -> Domain:
    """Read and check ``folder/domain.yml``; the tag is the folder's name."""
    from flowreel.project.bodies import parse_bodies
    from flowreel.yamlfile import read_yaml
    folder = Path(folder)
    path = folder / DOMAIN_FILE
    check = Checker(path)
    tag = check_tag(folder.name, Checker(path, ("tag",)))
    data = read_yaml(path)
    data = check.mapping({} if data is None else data, KEYS, required=("kind",))
    kind = check.at("kind").choice(data["kind"], KINDS)
    source = dict(check.at("source").mapping(data.get("source") or {}, _source_keys(kind)))
    for key in ("path",):
        if key in source:
            source[key] = str((folder / check.at("source", key).string(source[key])))
    if kind != "geometry" and "body" in source:
        body = source["body"]
        source["body"] = ({n: str(folder / f) for n, f in body.items()} if isinstance(body, dict)
                          else str(folder / body))
    if kind == "geometry" and "body" not in source:
        raise check.at("source").error("a geometry tag needs 'body' (the name of a body "
                                       "made in code, flowreel.sources.bodies)")
    units = {}
    for key, value in check.at("units").mapping(data.get("units") or {}, UNIT_KEYS).items():
        units[key] = check.at("units", key).number(value)
        if key != "p_inf" and units[key] <= 0:
            raise check.at("units", key).error(f"must be positive, got {units[key]:g}")
    bodies = parse_bodies(data.get("bodies"), check.at("bodies"), folder)
    measured = data.get("measured") or {}
    return Domain(tag, folder.resolve(), kind, source, units, bodies, dict(measured))


def _source_keys(kind: str) -> tuple:
    if kind == "geometry":
        return ("body", "params", "frames", "dt", "name")
    if kind == "vtk":
        return ("path", "body", "names", "body_block", "flow_block", "dt", "times", "name")
    return ("path", "volume", "body", "nen", "window", "margin", "cache", "name")


def domains(root: str | Path) -> dict[str, Domain]:
    """Every tag of the project at ``root``: the folders of ``data/`` holding a
    ``domain.yml``, by name."""
    data = Path(root) / "data"
    if not data.is_dir():
        return {}
    return {d.name: load_domain(d) for d in sorted(data.iterdir())
            if (d / DOMAIN_FILE).is_file()}
