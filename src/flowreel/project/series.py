"""Reading a body's declared time series from CSV (plan Section 5.4, "Series").

A series is a CSV file, whatever wrote it; for flexflow, FlexFlow Analyzer's
``data table --output`` (columns ``tsId, time, <variables>``). The result is a
``pandas.DataFrame`` with a ``time`` column first, in ascending time, then the value
columns, renamed as the declaration's ``columns`` say.

Where a restart repeats a time, the later row wins, as in the solver's own series.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from flowreel.project.bodies import Series


def read_series(spec: Series) -> pd.DataFrame:
    """The series ``spec`` as a frame: ``time``, then the values. Raises
    ``FileNotFoundError`` for a missing file and ``ValueError`` naming the file for a
    missing column."""
    frame = _read_one(spec.file, spec)
    frame = frame.drop_duplicates("time", keep="last").sort_values("time", kind="stable")
    return frame.reset_index(drop=True)


def _read_one(path: Path, spec: Series) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(2, f"series {spec.name!r}: no such file", str(path))
    raw = pd.read_csv(path, skipinitialspace=True)
    raw.columns = [str(c).strip() for c in raw.columns]
    wanted = {spec.time: "time", **{old: new for new, old in spec.columns.items()}}
    missing = [c for c in wanted if c not in raw.columns]
    if missing:
        raise ValueError(f"{path}: series {spec.name!r}: no column {missing[0]!r} "
                         f"(columns: {', '.join(raw.columns)})")
    frame = raw.rename(columns=wanted)
    return frame[["time"] + [c for c in frame.columns if c != "time"]]
