"""FlexFlow's time histories brought into a tag as CSV (plan Section 19.10, Phase 9
branch 3; ``flowreel data import history``).

A FlexFlow case writes its histories as text: probe data in ``othd_files/*.othd`` and
surface data in ``oisd_files/*.oisd``. Both are streams of timesteps, each a ``tsId``
and a ``time`` followed by named blocks::

    <name> <ncomp> <nnodes>
    v v v               <- nnodes lines of ncomp values

or a name with its value inline (``avePres 3.2e+02``). A file may hold several groups
(``othId`` in an OTHD file, ``osgId`` in an OISD file), one per probe set or surface:
everything after such a line belongs to that group, until the next one. Blocks before
any group line are group 0.

FlowReel reads them as FlexFlow Analyzer does (its ``core/history.py`` and
``core/readers/series.py``, borrowed here so FlowReel needs no FlexFlow code):

- **Which files, in what order.** The runs ``<stem>N.<ext>`` in the order of ``N``, from
  ``archive/`` and ``cleaned/`` (a ``cleaned/.runs.json`` record maps a cleaned file to
  the run it came from and lists the runs left out), then any in the older flat layout.
  Without numbered runs, the un-numbered files (the compiled ``<problem>.<ext>``).
- **Restarts.** A run that resumed earlier than the last one reached writes some times
  again; at a time written twice, the later run's values win.
- **Variables** are found by reading, not listed here: a case writes what its ``.def``
  asked for.

Each group becomes one CSV under the tag's ``series/``: ``othd_<group>.csv`` or
``oisd_<group>.csv``, with ``time``, then ``node`` when the group writes more than one
node, then a column per variable component (``aleDisp_x``, ``totTrac_y``, ``avePres``;
names of three components end in ``_x``, ``_y``, ``_z``).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

TYPES = ("othd", "oisd")
#: Bookkeeping lines, not variables.
STRUCTURAL = {"tsId", "time", "mask", "nOths", "othId", "othFlag", "nOsfs", "osgId", "osdFlag"}
GROUP_LINES = ("othId", "osgId")
_BLOCK = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+(\d+)\s+(\d+)\s*$")
_INLINE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+([-+0-9.][^\s]*)\s*$")
RUNS_RECORD = ".runs.json"
#: The series a group's CSV is declared as, when it holds these variables: name, the
#: variable, and the column names FlowReel's bodies use for its components.
KNOWN = {"othd": ("displacement", "aleDisp", ("dx", "dy", "dz")),
         "oisd": ("force", "totTrac", ("fx", "fy", "fz"))}


# ---- which files ------------------------------------------------------------------------

def _numbered(directory: Path, ext: str) -> dict[int, Path]:
    pattern = re.compile(rf"^.*?(\d+)\.{ext}$")
    found = {}
    if directory.is_dir():
        for path in directory.iterdir():
            m = pattern.match(path.name)
            if m and path.is_file():
                found[int(m.group(1))] = path
    return dict(sorted(found.items()))


def _record(cleaned: Path) -> tuple[dict, set]:
    try:
        data = json.loads((cleaned / RUNS_RECORD).read_text())
        return ({int(k): int(v) for k, v in data["cleaned"].items()},
                {int(n) for n in data.get("skipped", [])})
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}, set()


def run_files(folder: str | Path, ext: str) -> list[Path]:
    """The files of ``folder`` (an ``othd_files/`` or ``oisd_files/``) holding the whole
    history, in run order: a later file wins a time both have (see the module)."""
    folder = Path(folder)
    chosen, skipped = _record(folder / "cleaned")
    runs = {chosen.get(n, n): p for n, p in _numbered(folder / "cleaned", ext).items()}
    runs.update({n: p for n, p in _numbered(folder / "archive", ext).items() if n not in skipped})
    files = [runs[n] for n in sorted(runs)] + list(_numbered(folder, ext).values())
    if not files:
        files = sorted(p for p in folder.glob(f"*.{ext}") if p.is_file())
    return files


def history_folders(path: str | Path) -> dict[str, Path]:
    """The history folders of ``path``: a case folder holding ``othd_files/`` and
    ``oisd_files/``, or one such folder itself (or any folder of ``.othd``/``.oisd``)."""
    path = Path(path).expanduser().resolve()
    found = {}
    for ext in TYPES:
        if (path / f"{ext}_files").is_dir():
            found[ext] = path / f"{ext}_files"
        elif run_files(path, ext):
            found[ext] = path
    return found


# ---- reading ----------------------------------------------------------------------------

@dataclass
class Group:
    """One group of a history: its variables (name to ``(ncomp, nnodes)``, ``nnodes`` 0
    for an inline value) and its values by time (time to name to array)."""

    variables: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)

    @property
    def nodes(self) -> int:
        """The most nodes any of its variables writes (1 for surface data)."""
        return max((n for _, n in self.variables.values()), default=1) or 1

    def columns(self, name: str) -> list[str]:
        """The CSV columns of variable ``name``: itself, or ``_x``/``_y``/``_z`` (three
        components), or ``_0``, ``_1`` ... (any other count)."""
        ncomp = self.variables[name][0]
        if ncomp == 1:
            return [name]
        if ncomp == 3:
            return [f"{name}_{a}" for a in "xyz"]
        return [f"{name}_{i}" for i in range(ncomp)]


def read_history(files) -> dict[int, Group]:
    """Every group of ``files`` (in run order; a later file wins a time), by group id."""
    groups: dict[int, Group] = {}
    for path in files:
        with open(path) as f:
            lines = f.read().splitlines()
        i, n, time, group = 0, len(lines), None, 0
        while i < n:
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            head = line.split(None, 1)[0]
            if head == "time":
                time = round(float(line.split()[1]), 12)
                continue
            if head in GROUP_LINES:
                group = int(line.split()[1])
                continue
            if head in STRUCTURAL:
                continue
            block = _BLOCK.match(line)
            if block:
                name, ncomp, nnodes = block.group(1), int(block.group(2)), int(block.group(3))
                rows = lines[i:i + nnodes]
                i += nnodes
                if time is None:
                    continue
                values = np.array(" ".join(rows).split(), dtype=float)
                if values.size != ncomp * nnodes:
                    continue                                # a run cut off mid-block
                g = groups.setdefault(group, Group())
                g.variables.setdefault(name, (ncomp, nnodes))
                g.values.setdefault(time, {})[name] = values.reshape(nnodes, ncomp)
                continue
            inline = _INLINE.match(line)
            if inline and time is not None:
                g = groups.setdefault(group, Group())
                g.variables.setdefault(inline.group(1), (1, 0))
                g.values.setdefault(time, {})[inline.group(1)] = np.array([[float(inline.group(2))]])
    return dict(sorted(groups.items()))


def table(group: Group) -> pd.DataFrame:
    """A group as a long table: ``time``, ``node`` (with more than one node), values."""
    names = list(group.variables)
    nodes = group.nodes
    columns = [c for name in names for c in group.columns(name)]
    rows = []
    for time in sorted(group.values):
        at = group.values[time]
        block = np.full((nodes, len(columns)), np.nan)
        col = 0
        for name in names:
            ncomp, nn = group.variables[name]
            if name in at:
                v = at[name]
                block[:, col:col + ncomp] = v if nn == nodes else np.broadcast_to(v[:1], (nodes, ncomp))
            col += ncomp
        rows.append(np.column_stack([np.full(nodes, time), np.arange(nodes), block]))
    data = np.vstack(rows) if rows else np.empty((0, 2 + len(columns)))
    frame = pd.DataFrame(data, columns=["time", "node", *columns])
    frame["node"] = frame["node"].astype(int)
    return frame if nodes > 1 else frame.drop(columns="node")


# ---- into a tag -------------------------------------------------------------------------

@dataclass
class Converted:
    """One group written as CSV: its ``kind``, ``group`` id, ``file`` (from the tag's
    folder), ``rows``, the ``body`` it was declared under (or ``None``), and the series
    ``name`` and ``spec`` it is declared with."""

    kind: str
    group: int
    file: str
    rows: int
    nodes: int
    variables: list
    name: str
    spec: dict
    body: str | None = None


def series_spec(kind: str, group: int, frame: pd.DataFrame, file: str) -> tuple[str, dict]:
    """The series name and declaration of a group's CSV ``file``."""
    name, var, comps = KNOWN[kind]
    spec: dict = {"file": file}
    if "node" in frame.columns:
        spec["by"] = "node"
    have = [f"{var}_{a}" for a in "xyz"]
    if all(c in frame.columns for c in have):
        spec["columns"] = dict(zip(comps, have))
    else:
        name = f"{kind}_{group}"
    return name, spec


def convert(folder: Path, kind: str, files, out: str = "series") -> list[Converted]:
    """Read ``files`` and write each group's CSV under ``folder/out``."""
    target = folder / out
    target.mkdir(parents=True, exist_ok=True)
    done = []
    for gid, group in read_history(files).items():
        frame = table(group)
        rel = f"{out}/{kind}_{gid}.csv"
        frame.to_csv(folder / rel, index=False, float_format="%.10g")
        name, spec = series_spec(kind, gid, frame, rel)
        done.append(Converted(kind, gid, rel, len(frame), group.nodes, list(group.variables),
                              name, spec))
    return done
