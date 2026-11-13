"""Readers for FlexFlow's text time series: OTHD (probe displacements) and OISD (forces).

Both are text files of records. A record starts with a line ``time <t>`` and holds named
blocks: a header line ``<name> <n> <rows>`` followed by the rows. FlowReel reads

- ``aleDisp`` from ``othd_files/*.othd``: one row per probe node, the displacement;
- ``totTrac`` from ``oisd_files/*.oisd``: one row, the total force on the body.

Where restarts repeat a time, the later file (by modification time, then name) and the
later record win, as in the prototype's ``extract_series.py``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

AXES = ("x", "y", "z")


def records(path, block: str, rows_from_header: bool):
    """Yield ``(time, rows)`` for every ``block`` in the file at ``path``.

    ``rows`` is a list of lists of floats. With ``rows_from_header`` the third header
    field gives the number of rows; otherwise the block has one row.
    """
    with open(path) as f:
        time = None
        for line in f:
            if line.startswith("time "):
                time = float(line.split()[1])
                continue
            head = line.split()
            if time is None or len(head) != 3 or head[0] != block:
                continue
            n = int(head[2]) if rows_from_header else 1
            yield time, [[float(v) for v in next(f).split()] for _ in range(n)]


def _collect(files, block, rows_from_header):
    found = {}
    for path in sorted(files, key=lambda p: (p.stat().st_mtime, p.name)):
        for time, rows in records(path, block, rows_from_header):
            found[round(time, 6)] = rows
    return dict(sorted(found.items()))


def _columns(prefix: str, n: int) -> list[str]:
    return [f"{prefix}{AXES[i]}" if n <= 3 else f"{prefix}{i}" for i in range(n)]


def displacement(case: Path) -> pd.DataFrame:
    """Probe displacements from the case's OTHD files.

    Columns: ``time``, ``probe`` (row number in the block, from 0) and ``dx``, ``dy``,
    ``dz`` in the solver's length unit; one row per time and probe.
    """
    found = _collect(sorted(Path(case).glob("othd_files/*.othd")), "aleDisp", True)
    if not found:
        raise FileNotFoundError(f"no aleDisp records under {Path(case) / 'othd_files'}")
    width = len(next(iter(found.values()))[0])
    out = [[t, i, *row] for t, rows in found.items() for i, row in enumerate(rows)]
    frame = pd.DataFrame(out, columns=["time", "probe", *_columns("d", width)])
    return frame.astype({"probe": int})


def force(case: Path) -> pd.DataFrame:
    """Total force on the body from the case's OISD files.

    Columns: ``time`` and ``fx``, ``fy``, ``fz`` in the solver's units (not coefficients).
    """
    found = _collect(sorted(Path(case).glob("oisd_files/*.oisd")), "totTrac", False)
    if not found:
        raise FileNotFoundError(f"no totTrac records under {Path(case) / 'oisd_files'}")
    width = len(next(iter(found.values()))[0])
    table = np.array([[t, *rows[0]] for t, rows in found.items()])
    return pd.DataFrame(table, columns=["time", *_columns("f", width)])


SERIES = {"displacement": displacement, "force": force}
