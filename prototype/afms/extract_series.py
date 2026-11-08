"""Write the mid-span displacement, lift and drag of a case over the film window.

Usage: python extract_series.py CASE_DIR OUT_CSV [--t1 250 --t2 280]

Reads othd_files/*.othd (displacement of the 49 probe nodes along the span) and
oisd_files/*.oisd (total force on the cylinder), every time step. Where restarts
repeat a time, the later file and record win. The CSV is small, so the render
machine needs only it, not the OTHD and OISD files.
"""
import argparse
from pathlib import Path

import numpy as np

MID_ROW = 25  # probe at x = 6, from othd.riser_probe.map
Q, D, L = 500.0, 1.0, 12.0  # dynamic pressure, as in cyl.force_coeff; diameter; span


def records(path, t1, t2):
    """Yield (time, block name, rows) for every block within the window."""
    with open(path) as f:
        time = None
        for line in f:
            if line.startswith("time "):
                time = float(line.split()[1])
                continue
            if time is None or not (t1 - 1e-6 <= time <= t2 + 1e-6):
                continue
            head = line.split()
            if head and head[0] in ("aleDisp", "totTrac") and len(head) == 3:
                rows = int(head[2]) if head[0] == "aleDisp" else 1
                yield time, head[0], [next(f).split() for _ in range(rows)]


def series(files, name, pick, t1, t2):
    found = {}
    for path in sorted(files, key=lambda p: (p.stat().st_mtime, p.name)):
        for time, block, rows in records(path, t1, t2):
            if block == name:
                found[round(time, 6)] = pick(rows)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--t1", type=float, default=250.0)
    parser.add_argument("--t2", type=float, default=280.0)
    args = parser.parse_args()
    disp = series(list((args.case / "othd_files").glob("*.othd")), "aleDisp",
                  lambda rows: float(rows[MID_ROW][1]), args.t1, args.t2)
    force = series(list((args.case / "oisd_files").glob("*.oisd")), "totTrac",
                   lambda rows: [float(v) for v in rows[0]], args.t1, args.t2)
    times = sorted(set(disp) & set(force))
    if not times or times[-1] < args.t2 - 1e-6:
        raise SystemExit(f"data end at t = {times[-1] if times else None}, short of {args.t2}")
    table = np.array([[t, disp[t] / D, force[t][1] / (Q * D * L), force[t][2] / (Q * D * L)]
                      for t in times])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(args.out, table, delimiter=",", fmt="%.6f", header="t,y_over_D,CL,CD", comments="")
    print(f"{args.out}: {len(times)} steps, t {times[0]} to {times[-1]}")


if __name__ == "__main__":
    main()
