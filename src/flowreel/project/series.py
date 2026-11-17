"""Reading a body's declared time series from CSV (plan Section 5.4, "Series").

A series is a CSV file, whatever wrote it; for flexflow, FlexFlow Analyzer's
``data table --output`` (columns ``tsId, time, <variables>``). The result is a
``pandas.DataFrame`` with a ``time`` column first, in ascending time, then the value
columns, renamed as the declaration's ``columns`` say.

**At many points.** With ``by`` (say ``node``) the file is in long form: one row per time
and point, the column ``by`` numbering the points. The frame then has ``time``, the
``by`` column and, when ``stations`` are declared, a ``station`` column (where the point
is along the body). FlexFlow Analyzer writes one node per file today, so ``file`` may
hold ``{node}`` (the ``by`` name in braces): ``data/disp_{node}.csv`` reads every file
that matches, taking the point's number from the name.

Where a restart repeats a time, the later row wins, as in the solver's own series.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from flowreel.project.bodies import Series


def read_series(spec: Series) -> pd.DataFrame:
    """The series ``spec`` as a frame: ``time``, then (with ``by``) the point number and
    ``station``, then the values; ``frame.attrs["by"]`` names the point column. Raises ``FileNotFoundError`` for a missing file and
    ``ValueError`` naming the file for a missing column."""
    if spec.by is not None and "{" + spec.by + "}" in spec.file.name:
        frame = _read_per_point(spec)
    else:
        frame = _read_one(spec.file, spec)
    keys = ["time"] if spec.by is None else ["time", spec.by]
    frame = frame.drop_duplicates(keys, keep="last").sort_values(keys, kind="stable")
    if spec.by is not None and spec.stations is not None:
        frame.insert(2, "station", _stations(spec, frame[spec.by]))
    frame = frame.reset_index(drop=True)
    frame.attrs["by"] = spec.by                  # the point numbers: not a value column
    return frame


def _read_one(path: Path, spec: Series) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(2, f"series {spec.name!r}: no such file", str(path))
    raw = pd.read_csv(path, skipinitialspace=True)
    raw.columns = [str(c).strip() for c in raw.columns]
    wanted = {spec.time: "time", **{old: new for new, old in spec.columns.items()}}
    missing = [c for c in wanted if c not in raw.columns]
    if spec.by is not None and "{" + spec.by + "}" not in spec.file.name and spec.by not in raw.columns:
        missing.append(spec.by)
    if missing:
        raise ValueError(f"{path}: series {spec.name!r}: no column {missing[0]!r} "
                         f"(columns: {', '.join(raw.columns)})")
    frame = raw.rename(columns=wanted)
    first = ["time"] + ([spec.by] if spec.by in frame.columns else [])
    return frame[first + [c for c in frame.columns if c not in first]]


def _read_per_point(spec: Series) -> pd.DataFrame:
    """Every file matching ``spec.file`` with ``{by}`` replaced by a whole number."""
    marker = "{" + spec.by + "}"
    head, tail = spec.file.name.split(marker, 1)
    pattern = re.compile(re.escape(head) + r"(-?\d+)" + re.escape(tail) + r"$")
    found = sorted((int(m.group(1)), p) for p in spec.file.parent.glob(head + "*" + tail)
                   if (m := pattern.match(p.name)))
    if not found:
        raise FileNotFoundError(2, f"series {spec.name!r}: no file matches", str(spec.file))
    frames = []
    for number, path in found:
        one = _read_one(path, spec)
        one.insert(1, spec.by, number)
        frames.append(one)
    return pd.concat(frames, ignore_index=True)


def _stations(spec: Series, points: pd.Series) -> np.ndarray:
    """Station of each row's point: a list in the order of the sorted point numbers, or a
    CSV with the ``by`` column and a ``station`` column."""
    numbers = np.sort(points.unique())
    if isinstance(spec.stations, tuple):
        if len(spec.stations) != len(numbers):
            raise ValueError(f"series {spec.name!r}: {len(spec.stations)} stations for "
                             f"{len(numbers)} points ({spec.by} {numbers[0]} to {numbers[-1]})")
        table = dict(zip(numbers.tolist(), spec.stations))
    else:
        path = Path(spec.stations)
        if not path.is_file():
            raise FileNotFoundError(2, f"series {spec.name!r}: no stations file", str(path))
        raw = pd.read_csv(path, skipinitialspace=True)
        raw.columns = [str(c).strip() for c in raw.columns]
        for col in (spec.by, "station"):
            if col not in raw.columns:
                raise ValueError(f"{path}: no column {col!r} (columns: {', '.join(raw.columns)})")
        table = dict(zip(raw[spec.by].astype(int).tolist(), raw["station"].astype(float)))
    lost = [n for n in numbers.tolist() if n not in table]
    if lost:
        raise ValueError(f"series {spec.name!r}: no station for {spec.by} {lost[0]}")
    return points.map(table).to_numpy(dtype=float)
