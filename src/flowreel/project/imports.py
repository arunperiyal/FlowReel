"""Bringing a case into a project as a tag, and looking after the tags (plan Section
19.10, Phase 9 branch 2; ``flowreel data import|list|info|remove|rename|check``).

**Import.** ``import_data(root, "plt", PATH, "bare")`` links the folder the case's PLT
files are in as ``data/bare/plt`` (``vtk``: the folder of its flow files, as
``data/<tag>/vtk``; ``geometry``: nothing to link) and writes ``data/bare/domain.yml``
with what it measured: the kind, the reader's options, every wall zone as a body with its
axis and diameter, and ``measured:`` (steps, times, zones, fields, bounds), with the
units left to fill. Nothing is copied unless ``copy``: then the files that would be
linked are copied, after their size is said (above :data:`COPY_LIMIT` it asks for
``yes``), and their SHA-256 sums are kept under ``measured.checksums``.

A tag that already holds a flow of the same kind is refused unless ``force``, which
replaces the link and the ``measured:`` block but keeps the rest of ``domain.yml``, edits
and all; a tag of another flow kind is refused.
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from flowreel.project.domain import DOMAIN_FILE, KINDS, check_tag, load_domain
from flowreel.scene.errors import Checker

#: Above this many bytes, ``--copy`` asks for ``--yes``.
COPY_LIMIT = 5 * 1024 ** 3
MEASURED = "measured:"


class DataError(ValueError):
    """An import that cannot be done as asked (a message for the user)."""


@dataclass
class Imported:
    """What an import did: the tag's ``folder``, the ``kind``, what was ``linked`` or
    ``copied`` (and how many bytes), and the ``domain`` file written or updated."""

    folder: Path
    kind: str
    linked: list = field(default_factory=list)
    copied: list = field(default_factory=list)
    nbytes: int = 0
    domain: Path | None = None
    updated: bool = False


def _data(root: Path) -> Path:
    return Path(root) / "data"


def tag_folder(root, tag: str) -> Path:
    """``root/data/<tag>``, the name checked."""
    check_tag(tag, Checker(None, ("tag",)))
    return _data(root) / tag


def _flow_files(kind: str, path: Path) -> list[Path]:
    if kind == "plt":
        files = sorted(path.glob("*.plt"))
        if not files:
            raise DataError(f"no .plt files in {path} (give the folder the PLT files are in)")
        return files
    files = sorted(p for p in path.iterdir() if p.suffix in (".pvd", ".vtu", ".vti", ".vtp",
                                                              ".vtk", ".vtm", ".pvtu"))
    if not files:
        raise DataError(f"no VTK files in {path}")
    return files


def _vtk_flow(path: Path, flow: str | None) -> str:
    """The flow file within ``path``: ``flow`` if given, else the one ``.pvd``."""
    if flow:
        if not (path / flow).exists():
            raise DataError(f"no {flow} in {path}")
        return flow
    pvds = sorted(p.name for p in path.glob("*.pvd"))
    if len(pvds) == 1:
        return pvds[0]
    raise DataError(f"{path}: give --flow FILE (the .pvd, a pattern such as flow_*.vtu, "
                       f"or one file); " + (f"several .pvd: {', '.join(pvds)}" if pvds
                                             else "no .pvd found"))


def _size(files) -> int:
    return sum(f.stat().st_size for f in files)


def _copy(files: list[Path], target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    sums = {}
    for f in files:
        h = hashlib.sha256()
        with open(f, "rb") as src, open(target / f.name, "wb") as out:
            for block in iter(lambda: src.read(1 << 20), b""):
                h.update(block)
                out.write(block)
        sums[f.name] = h.hexdigest()
    return sums


def human(n: float) -> str:
    """``n`` bytes as ``1.2 GB``."""
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def import_data(root, kind: str, path: str | Path | None, tag: str, *,
                bodies: dict | None = None, flow: str | None = None,
                function: str | None = None, params: dict | None = None,
                copy: bool = False, yes: bool = False, force: bool = False,
                say=print) -> Imported:
    """Import a case as ``tag`` of the project at ``root`` (see the module)."""
    if kind not in KINDS:
        raise DataError(f"unknown kind {kind!r} (one of: {', '.join(KINDS)})")
    folder = tag_folder(root, tag)
    domain_file = folder / DOMAIN_FILE
    old = load_domain(folder) if domain_file.is_file() else None
    if old is not None and old.kind != kind:
        raise DataError(f"tag {tag!r} holds a {old.kind} case; a tag holds one case "
                           f"(import it under another tag)")
    if old is not None and not force:
        raise DataError(f"tag {tag!r} holds a {kind} case already (use --force to "
                           f"replace its {'link' if kind != 'geometry' else 'body'}; "
                           f"domain.yml keeps your edits)")
    done = Imported(folder, kind)
    folder.mkdir(parents=True, exist_ok=True)
    source: dict = {}
    checksums = {}
    if kind == "geometry":
        if not function:
            raise DataError("a geometry tag needs --name FUNCTION (a body made in code)")
        source = {"body": function, "params": dict(params or {})}
    else:
        if path is None:
            raise DataError(f"give --path: the folder the {kind.upper()} files are in")
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            raise DataError(f"{path} is not a folder (give the folder the files are in)")
        files = _flow_files(kind, path)
        target = folder / kind
        if copy:
            body_files = [Path(f).expanduser().resolve() for f in (bodies or {}).values()]
            nbytes = _size(files) + _size(body_files)
            say(f"{len(files)} files, {human(nbytes)} to copy into {target}")
            if nbytes > COPY_LIMIT and not yes:
                raise DataError(f"{human(nbytes)} is more than {human(COPY_LIMIT)}: add "
                                   f"--yes to copy it, or import it as a link")
            if target.is_symlink() or target.exists():
                _remove(target)
            checksums = _copy(files, target)
            done.copied, done.nbytes = [str(target)], nbytes
        else:
            if target.is_symlink() or target.exists():
                _remove(target)
            target.symlink_to(path, target_is_directory=True)
            done.linked.append(str(target))
        if kind == "plt":
            source = {"path": "plt"}
        else:
            source = {"path": f"vtk/{_vtk_flow(path, flow)}"}
            if bodies:
                named = {}
                for name, file in bodies.items():
                    file = Path(file).expanduser().resolve()
                    if not file.is_file():
                        raise DataError(f"no body file {file}")
                    if file.parent == path or path in file.parents:
                        named[name] = f"vtk/{file.relative_to(path)}"
                    else:
                        own = folder / f"{name}{file.suffix}"
                        if own.is_symlink() or own.exists():
                            own.unlink()
                        if copy:
                            shutil.copy2(file, own)
                            checksums[own.name] = _sha256(own)
                        else:
                            own.symlink_to(file)
                            done.linked.append(str(own))
                        named[name] = own.name
                source["body"] = named
    measured, body_text = _measure(folder, kind, source)
    if checksums:
        measured["checksums"] = checksums
    if old is not None and old.measured.get("history"):
        measured["history"] = old.measured["history"]       # data import history's
    if old is None:
        domain_file.write_text(_domain_text(tag, kind, source, body_text, measured))
    else:
        _replace_measured(domain_file, measured, kind, source)
        done.updated = True
    done.domain = domain_file
    return done


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def _measure(folder: Path, kind: str, source: dict) -> tuple[dict, str]:
    """What the case is (``measured:``) and its bodies' YAML, measured at the first step."""
    from flowreel import sources
    from flowreel.project.init import body_block
    options = dict(source)
    if "path" in options:
        options["path"] = str(folder / options["path"])
    if isinstance(options.get("body"), dict) and kind == "vtk":
        options["body"] = {n: str(folder / f) for n, f in options["body"].items()}
    opened = sources.create(kind, **options)
    steps = list(opened.steps())
    first = steps[0]
    zones = list(opened.bodies())
    measured = {"steps": {"first": int(first), "last": int(steps[-1]), "count": len(steps)},
                "times": [float(opened.time(first)), float(opened.time(steps[-1]))],
                "zones": zones, "fields": list(opened.fields())}
    try:
        box = opened.bounds()
        measured["bounds"] = [[round(float(a), 6), round(float(b), 6)]
                              for a, b in zip(box.lo, box.hi)]
    except (LookupError, AttributeError, ValueError):
        pass
    blocks = []
    for z in zones:
        try:
            block = body_block(z, opened.body(first, z))
        except (LookupError, ValueError):
            continue
        blocks.append(block.replace("{file: data/" + z + "_displacement.csv}",
                                    "{file: series/" + z + "_displacement.csv}"))
    return measured, "\n".join(blocks)


def _measured_text(measured: dict) -> str:
    return MEASURED + "                         # what data import found; not read back\n" + \
        "\n".join("  " + line for line in yaml.safe_dump(measured, sort_keys=False,
                                                          default_flow_style=None,
                                                          width=88).splitlines())


def _domain_text(tag: str, kind: str, source: dict, bodies: str, measured: dict) -> str:
    src = yaml.safe_dump({"source": source}, sort_keys=False, default_flow_style=None).rstrip()
    return "\n".join([
        f"# domain.yml of the tag {tag!r}, written by `flowreel data import` and edited by hand",
        "# (a second import with --force keeps your edits). Reference:",
        "# docs/guide/projects/data.md.",
        f"kind: {kind}",
        src,
        "units:                           # the case's constants: fill in what you know",
        "  # rho: 1.0                     # density",
        "  # mu: 1.0                      # dynamic viscosity (wall shear, sectional force)",
        "  # u_inf: 1.0                   # free-stream speed",
        "  # length: 1.0                  # the length lengths are shown in",
        "bodies:" + ("" if bodies else " {}                       # no surface zone found"),
        *( [bodies] if bodies else [] ),
        _measured_text(measured),
    ]) + "\n"


def _replace_measured(path: Path, measured: dict, kind: str, source: dict) -> None:
    """Replace the ``measured:`` block (and the reader's options) of an existing
    ``domain.yml``, keeping every other line as it was."""
    text = path.read_text()
    head = text.split("\n" + MEASURED, 1)[0] if ("\n" + MEASURED) in text else text.rstrip()
    data = yaml.safe_load(head) or {}
    if data.get("source") != source:
        lines = head.splitlines()
        start = next((i for i, l in enumerate(lines) if l.startswith("source:")), None)
        if start is not None:
            end = start + 1
            while end < len(lines) and lines[end].startswith((" ", "\t")):
                end += 1
            new = yaml.safe_dump({"source": source}, sort_keys=False,
                                 default_flow_style=None).rstrip().splitlines()
            lines[start:end] = new
            head = "\n".join(lines)
    path.write_text(head.rstrip() + "\n" + _measured_text(measured) + "\n")


# ---- histories ------------------------------------------------------------------------

HISTORY_NOTE = "history groups not given to a body: move each under its body's series"


def import_history(root, path, tag: str, *, groups: dict | None = None, copy: bool = False,
                   yes: bool = False, force: bool = False, say=print) -> list:
    """Bring a FlexFlow case's OTHD and OISD files into the existing ``tag``: link
    ``othd_files/`` as ``data/TAG/othd`` (and ``oisd``), convert each group once to CSV
    under ``series/`` (:mod:`flowreel.project.history`) and declare it under its body:
    the one body, when the tag has one body and the file one group, else as ``groups``
    names (group id to body; the same id in either kind). Groups left over are listed in
    ``domain.yml`` as comments, to move by hand. Returns the
    :class:`~flowreel.project.history.Converted` groups."""
    from flowreel.project.domain import declare_series, note_lines
    from flowreel.project.history import convert, history_folders, run_files
    folder = tag_folder(root, tag)
    if not (folder / DOMAIN_FILE).is_file():
        raise DataError(f"no tag {tag!r}: import its flow first (data import plt|vtk ... "
                        f"--tag {tag}), then its history")
    domain = load_domain(folder)
    if path is None:
        raise DataError("give --path: the case folder (holding othd_files/ and oisd_files/), "
                        "or one of those folders")
    found = history_folders(path)
    if not found:
        raise DataError(f"no .othd or .oisd files in {Path(path).expanduser()} (nor in its "
                        f"othd_files/ or oisd_files/)")
    taken = [k for k in found if (folder / k).is_symlink() or (folder / k).exists()]
    if taken and not force:
        raise DataError(f"tag {tag!r} has its {' and '.join(taken)} history already (use "
                        f"--force to replace it and its series)")
    groups = dict(groups or {})
    for g, body in groups.items():
        if body not in domain.bodies:
            raise DataError(f"--group {g}={body}: tag {tag!r} has no body {body!r} "
                            f"(bodies: {', '.join(domain.bodies) or 'none'})")
    converted, measured = [], {}
    for kind, source in found.items():
        files = run_files(source, kind)
        target = folder / kind
        if target.is_symlink() or target.exists():
            _remove(target)
        if copy:
            nbytes = _size(files)
            say(f"{len(files)} {kind} files, {human(nbytes)} to copy into {target}")
            if nbytes > COPY_LIMIT and not yes:
                raise DataError(f"{human(nbytes)} is more than {human(COPY_LIMIT)}: add --yes "
                                f"to copy it, or import it as a link")
            _copy(files, target)
            files = [target / f.name for f in files]
        else:
            target.symlink_to(source, target_is_directory=True)
        done = convert(folder, kind, files)
        only = len(done) == 1 and len(domain.bodies) == 1
        for c in done:
            c.body = groups.get(c.group, next(iter(domain.bodies)) if only else None)
        converted += done
        measured[kind] = {"files": [f.name for f in files],
                          "groups": {c.group: {"rows": c.rows, "nodes": c.nodes,
                                               "variables": c.variables} for c in done}}
    seen = {}
    for c in converted:
        if c.body is None:
            continue
        if (c.body, c.name) in seen:
            raise DataError(f"{c.body} would get two {c.name} series ({seen[c.body, c.name]} "
                            f"and {c.kind} {c.group}): give each group its body with --group")
        seen[c.body, c.name] = f"{c.kind} {c.group}"
    for c in converted:
        if c.body is not None:
            try:
                declare_series(folder, c.body, c.name, c.spec, force=force)
            except ValueError as exc:
                raise DataError(str(exc)) from None
    import yaml
    left = [f"{c.kind} {c.group} ({c.name}): " + yaml.safe_dump(
        c.spec, default_flow_style=True, width=10000, sort_keys=False).strip()
        for c in converted if c.body is None]
    note_lines(folder, HISTORY_NOTE, left)
    raw = yaml.safe_load((folder / DOMAIN_FILE).read_text()) or {}
    old = dict(raw.get("measured") or {})
    old["history"] = {**(old.get("history") or {}), **measured}
    _replace_measured(folder / DOMAIN_FILE, old, domain.kind, raw.get("source") or {})
    return converted


# ---- the other actions ----------------------------------------------------------------

@dataclass
class TagState:
    """One tag as ``data list`` and ``data check`` see it: its ``kind``, its steps (or
    ``None``), what its flow link points at and whether it resolves, its size in bytes,
    and ``problems`` found."""

    tag: str
    kind: str | None
    steps: tuple | None = None
    target: str | None = None
    resolves: bool = True
    nbytes: int = 0
    problems: list = field(default_factory=list)


def _bytes_under(path: Path) -> int:
    total = 0
    for p in path.rglob("*") if path.is_dir() else [path]:
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def state(root, tag: str, deep: bool = False) -> TagState:
    """``tag``'s state; ``deep`` also opens its source and checks its units and series."""
    from flowreel.project.domain import open_tag
    folder = tag_folder(root, tag)
    out = TagState(tag, None)
    try:
        domain = load_domain(folder)
    except Exception as exc:                            # noqa: BLE001 (said, not raised)
        out.problems.append(f"domain.yml: {exc}")
        return out
    out.kind = domain.kind
    link = folder / domain.kind
    if domain.kind != "geometry":
        if link.is_symlink():
            out.target = str(link.readlink())
            out.resolves = link.exists()
        elif link.is_dir():
            out.target = "(copied)"
        else:
            out.resolves = False
        if not out.resolves:
            out.problems.append(f"{domain.kind}/ does not resolve ({out.target or 'missing'}): "
                                f"the case moved? import it again with --force")
        else:
            out.nbytes = _bytes_under(link)
    m = domain.measured.get("steps") or {}
    if m:
        out.steps = (m.get("first"), m.get("last"), m.get("count"))
    if deep:
        if out.resolves:
            try:
                source = open_tag(domain)
                steps = list(source.steps())
                out.steps = (steps[0], steps[-1], len(steps))
            except Exception as exc:                    # noqa: BLE001
                out.problems.append(f"the {domain.kind} source does not open: {exc}")
        missing = [k for k in ("rho", "mu", "u_inf") if k not in domain.units]
        if missing and domain.kind != "geometry":
            out.problems.append(f"units not given: {', '.join(missing)} (needed by "
                                f"coefficients and wall fields)")
        for name, body in domain.bodies.items():
            for sname, s in body.series.items():
                if "{" not in s.file.name and not s.file.is_file():
                    out.problems.append(f"bodies.{name}.series.{sname}: no file {s.file}")
    return out


def tags(root) -> list[str]:
    """The tags under ``root/data/`` (folders with a ``domain.yml``)."""
    data = _data(root)
    return sorted(d.name for d in data.iterdir() if (d / DOMAIN_FILE).is_file()) \
        if data.is_dir() else []


def remove(root, tag: str) -> list[str]:
    """Remove ``tag``'s folder: its links (never what they point at), its ``domain.yml``
    and what FlowReel wrote in it; returns what was removed."""
    folder = tag_folder(root, tag)
    if not (folder / DOMAIN_FILE).is_file():
        raise DataError(f"no tag {tag!r} (tags: {', '.join(tags(root)) or 'none'})")
    removed = [str(p.relative_to(folder)) for p in sorted(folder.iterdir())]
    shutil.rmtree(folder)                                # a link is removed, not followed
    return removed


#: Files of a project that may name a tag.
NAMING = ("flowreel.yml", "film.yml", "shots", "panels", "layouts")


def rename(root, old: str, new: str) -> list[Path]:
    """Rename tag ``old`` to ``new``: its folder, and every file of the project that names
    it (``source: old``, ``tag: old``, ``old.body``, and ``tags:`` in ``flowreel.yml``);
    returns the files changed."""
    import re
    root = Path(root)
    src, dst = tag_folder(root, old), tag_folder(root, new)
    if not (src / DOMAIN_FILE).is_file():
        raise DataError(f"no tag {old!r} (tags: {', '.join(tags(root)) or 'none'})")
    if dst.exists():
        raise DataError(f"tag {new!r} exists already")
    src.rename(dst)
    word = re.escape(old)
    patterns = [
        (re.compile(rf"(\b(?:source|tag):\s*){word}(?=\s*(?:[,}}#\n]|$))", re.M), rf"\g<1>{new}"),
        (re.compile(rf"(?<![\w.-]){word}\.(?=[A-Za-z_])"), f"{new}."),
    ]
    changed = []
    files = []
    for name in NAMING:
        p = root / name
        files += [p] if p.is_file() else sorted(p.rglob("*.yml")) if p.is_dir() else []
    for p in files:
        text = p.read_text()
        out = text
        for rx, rep in patterns:
            out = rx.sub(rep, out)
        if p.name == "flowreel.yml":
            out = re.sub(rf"(tags:\s*\[[^\]]*?)(?<![\w-]){word}(?![\w-])", rf"\g<1>{new}", out)
        if out != text:
            p.write_text(out)
            changed.append(p)
    return changed


def describe(path_or_domain) -> list[str]:
    """Lines saying what a case is: a tag's domain, or a folder outside any project (its
    kind guessed from the files in it)."""
    from flowreel import sources
    from flowreel.project.domain import Domain, open_tag
    if isinstance(path_or_domain, Domain):
        d = path_or_domain
        source = open_tag(d)
        lines = [f"tag {d.tag}: {d.kind}, {d.folder}"]
    else:
        path = Path(path_or_domain).expanduser().resolve()
        if list(path.glob("*.plt")) or (path / "binary").is_dir():
            source = sources.create("plt", path=str(path))
            kind = "plt"
        else:
            pvds = sorted(path.glob("*.pvd"))
            if len(pvds) != 1:
                raise DataError(f"{path}: not a folder of PLT files, nor of VTK files "
                                   f"with one .pvd")
            source = sources.create("vtk", path=str(pvds[0]))
            kind = "vtk"
        lines = [f"{path}: {kind}"]
        d = None
    steps = list(source.steps())
    lines.append(f"steps:  {len(steps)}, {steps[0]} to {steps[-1]} (t = "
                 f"{source.time(steps[0]):g} to {source.time(steps[-1]):g})")
    lines.append(f"zones:  {', '.join(source.bodies()) or 'none'}")
    lines.append(f"fields: {', '.join(source.fields())}")
    try:
        box = source.bounds()
        lines.append("bounds: " + ", ".join(f"{a}: {lo:g} to {hi:g}" for a, lo, hi in
                                            zip("xyz", box.lo, box.hi)))
    except (LookupError, AttributeError, ValueError):
        pass
    if d is not None:
        lines.append("units:  " + (", ".join(f"{k} {v:g}" for k, v in d.units.items())
                                   or "none given"))
        for name, body in d.bodies.items():
            series = ", ".join(body.series) or "no series"
            lines.append(f"body {name}: zone {body.zone}, axis {body.axis or '?'}, "
                         f"diameter {body.diameter if body.diameter else '?'}; {series}")
    return lines
