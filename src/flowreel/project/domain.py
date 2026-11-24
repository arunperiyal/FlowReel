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


def open_tag(domain: Domain, **options):
    """The source of ``domain``: its kind's adapter with its ``source`` options (and any
    ``options`` given, which win), its bodies declared on it, and its units as
    ``source.units``."""
    from flowreel import sources
    from flowreel.project.names import DeclaredSource
    opened = sources.create(domain.kind, **{**domain.source, **options})
    tagged = DeclaredSource(opened, domain.bodies)
    tagged.units = dict(domain.units)
    tagged.tag = domain.tag
    return tagged


def template(kind: str = "plt") -> str:
    """The text of a ``domain.yml`` of ``kind`` with every key, at its default or as an
    example, each with a comment (``flowreel data template``)."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r} (one of: {', '.join(KINDS)})")
    head = [
        "# domain.yml: one case of the project, under data/<tag>/ (written by `flowreel data",
        "# import`, edited by hand). Reference: docs/guide/projects/data.md.",
        f"kind: {kind:<30}# plt, vtk or geometry: how the case is read",
    ]
    if kind == "plt":
        source = ["source:",
                  "  path: plt                       # the folder of <name>.<step>.plt files (a link)",
                  "  # volume: fluid                 # the volume zone; default the first of tetrahedra or bricks",
                  "  # body: cyl                     # wall zone(s); default every zone of triangles or quadrilaterals",
                  "  # margin: 0.0                   # grow a crop's window by this much (long bodies)"]
    elif kind == "vtk":
        source = ["source:",
                  "  path: vtk/flow.pvd              # the flow: a .pvd, a pattern (flow_*.vtu) or one file",
                  "  # body: {cylinder: vtk/cylinder.vtp}   # body files, by name",
                  "  # names: {U: velocity}          # the files' array names for the standard ones"]
    else:
        source = ["source:",
                  "  body: grooved_cylinder          # a body made in code (flowreel.sources.bodies)",
                  "  params: {}                      # its parameters",
                  "  # frames: 1                     # steps 0 .. frames-1",
                  "  # dt: 1.0                       # time of one step"]
    rest = [
        "units:                            # the case's constants, in its own units",
        "  # rho: 1000.0                   # density",
        "  # mu: 1.0                       # dynamic viscosity (wall shear, sectional force)",
        "  # u_inf: 1.0                    # free-stream speed",
        "  # p_inf: 0.0                    # free-stream pressure",
        "  # length: 1.0                   # the length lengths are shown in (axes in diameters)",
        "bodies:                           # by name, as shots of this tag call them",
        "  # cyl:",
        "  #   zone: cyl                   # the wall zone (a file, for vtk: see source.body)",
        "  #   axis: x                     # along the body",
        "  #   diameter: 1.0",
        "  #   ends: [{at: 0.0, support: clamped}, {at: 12.0, support: clamped}]",
        "  #   series:                     # time histories, CSV, paths from this folder",
        "  #     force: {file: series/force.csv}",
        "# measured: {}                    # what data import found; not read",
    ]
    return "\n".join(head + source + rest) + "\n"


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def declare_series(folder: str | Path, body: str, name: str, spec: dict,
                   force: bool = False) -> None:
    """Declare ``spec`` as the series ``name`` of ``body`` in ``folder/domain.yml``,
    changing only the lines of that series, so the file's comments and edits stay.
    A series of that name already there is replaced only with ``force``. Raises
    ``ValueError`` (no such body, the name taken) or the loader's error, leaving the
    file as it was."""
    import yaml
    path = Path(folder) / DOMAIN_FILE
    old = path.read_text()
    lines = old.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^bodies\s*:", l)), None)
    if start is None:
        raise ValueError(f"{path}: no bodies: to declare {name} under")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and _indent(lines[i]) == 0), len(lines))
    flow = re.compile(rf"^  {re.escape(body)}\s*:\s*(\{{.*\}})\s*(#.*)?$")
    for i in range(start + 1, end):
        m = flow.match(lines[i])
        if m:                                   # a body in flow style: write it as a block
            items = yaml.safe_load(m.group(1)) or {}
            lines[i:i + 1] = [f"  {body}:" + (f"  {m.group(2)}" if m.group(2) else "")] + [
                f"    {k}: " + yaml.safe_dump(v, default_flow_style=True, width=10000).strip()
                .removesuffix("...").strip() for k, v in items.items()]
            end += len(items)
            break
    key = re.compile(rf"^  {re.escape(body)}\s*:\s*(#.*)?$")
    at = next((i for i in range(start + 1, end) if key.match(lines[i])), None)
    if at is None:
        names = [l.split(":")[0].strip() for l in lines[start + 1:end]
                 if _indent(l) == 2 and not l.lstrip().startswith("#") and ":" in l]
        raise ValueError(f"{path}: no body {body!r} to declare {name} under "
                         f"(bodies: {', '.join(names) or 'none'})")
    stop = next((i for i in range(at + 1, end) if lines[i].strip() and _indent(lines[i]) <= 2),
                end)
    entry = f"      {name}: " + yaml.safe_dump(spec, default_flow_style=True, width=10000,
                                                sort_keys=False).strip()
    series = next((i for i in range(at + 1, stop)
                   if re.match(r"^    series\s*:", lines[i])), None)
    if series is None:
        lines[stop:stop] = ["    series:", entry]
    else:
        if re.match(r"^    series\s*:\s*\{\s*\}", lines[series]):
            lines[series] = "    series:"
        rows_end = next((i for i in range(series + 1, stop)
                         if lines[i].strip() and _indent(lines[i]) <= 4
                         and not lines[i].lstrip().startswith("#")), stop)
        mine = re.compile(rf"^      {re.escape(name)}\s*:")
        there = next((i for i in range(series + 1, rows_end) if mine.match(lines[i])), None)
        if there is not None:
            if not force:
                raise ValueError(f"{path}: {body} has a series {name!r} already "
                                 f"(--force replaces it)")
            after = next((i for i in range(there + 1, rows_end)
                          if lines[i].strip() and _indent(lines[i]) <= 6), rows_end)
            lines[there:after] = [entry]
        else:
            last = max((i for i in range(series + 1, rows_end)
                        if lines[i].strip() and not lines[i].lstrip().startswith("#")),
                       default=series)
            lines.insert(last + 1, entry)
    path.write_text("\n".join(lines) + "\n")
    try:
        load_domain(folder)
    except Exception:
        path.write_text(old)
        raise


def note_lines(folder: str | Path, title: str, notes: list[str]) -> None:
    """Put ``notes`` as comments under a ``# title`` line in ``folder/domain.yml``, before
    ``measured:``, replacing an earlier note of the same title."""
    path = Path(folder) / DOMAIN_FILE
    lines = path.read_text().splitlines()
    head = f"# {title}"
    if head in lines:
        i = lines.index(head)
        j = i + 1
        while j < len(lines) and lines[j].startswith("#   "):
            j += 1
        del lines[i:j]
    if notes:
        at = next((i for i, l in enumerate(lines) if l.startswith("measured:")), len(lines))
        lines[at:at] = [head, *("#   " + n for n in notes)]
    path.write_text("\n".join(lines) + "\n")
