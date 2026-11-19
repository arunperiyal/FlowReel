"""Write the generated data of the comparison example: two cases, bare and helical.

Needs no data and no solver: everything is made from formulas, at test time or when
``run.py`` asks, and never checked in. Times are in ``tU/D``.

``write_data(folder)`` writes:

- ``data/<case>_series.csv``: mid-span displacement, lift and drag every ``DT``, from 0
  to ``T_END``, in the prototype's own format (``t, y_over_D, CL, CD``), so the
  prototype's ``compose_compare.py`` reads the same file;
- ``data/<case>_lift.csv``: sectional lift at ``STRIPS`` strips along a span of
  ``SPAN``, in long form (``time, strip, cl``), and ``data/strips.csv`` (``strip,
  station``), the strip centres;
- ``frames/<case>_wake/frame_NNNNN.png``: ``len(WAKE_TIMES)`` stand-in wake frames,
  1280 x 540, a pattern that moves from frame to frame (the flow shots of a real film).

The helical case moves and lifts less than the bare one, as grooves would make it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

CASES = {"bare": (0.55, 1.1, 1.25), "helical": (0.08, 0.25, 1.05)}   # y, CL, CD amplitudes
DT = 0.05
T_END = 8.0
SPAN = 12.0
STRIPS = 24
FREQ = 0.2                     # shedding frequency, in U/D
WAKE_TIMES = [round(2.02 + 0.25 * k, 6) for k in range(24)]
WAKE_SIZE = (1280, 540)


def times() -> np.ndarray:
    return np.round(np.arange(0, T_END + 1e-9, DT), 6)


def series(case: str, t: np.ndarray) -> np.ndarray:
    """``(len(t), 3)``: displacement, lift and drag of ``case``."""
    y, cl, cd = CASES[case]
    w = 2 * np.pi * FREQ
    grow = 1 - np.exp(-t / 1.5)
    return np.column_stack([y * grow * np.sin(w * t - 0.6), cl * grow * np.sin(w * t),
                            cd + 0.15 * cl * grow * np.sin(2 * w * t)])


def stations() -> np.ndarray:
    """The strips' centres along the span."""
    return (np.arange(STRIPS) + 0.5) * SPAN / STRIPS


def sectional_lift(case: str, t: np.ndarray) -> np.ndarray:
    """``(len(t), STRIPS)``: lift along the span, the first bending mode's shape for the
    bare case, and cells of shedding out of phase along the span for the helical one."""
    _, cl, _ = CASES[case]
    s = stations()[None, :]
    tt = t[:, None]
    w = 2 * np.pi * FREQ
    grow = 1 - np.exp(-tt / 1.5)
    if case == "bare":
        return 1.4 * grow * np.sin(np.pi * s / SPAN) * np.sin(w * tt)
    return 1.2 * grow * np.sin(w * tt - 2 * np.pi * s / 4.0) * (0.4 + 0.6 * np.sin(np.pi * s / SPAN))


def wake(case: str, k: int) -> np.ndarray:
    """Frame ``k`` of ``case``'s stand-in wake: ``(540, 1280, 3)`` uint8."""
    from flowreel.colours import FIRE_ICE
    w, h = WAKE_SIZE
    y, cl, _ = CASES[case]
    x = np.arange(w)[None, :] / w
    yy = (np.arange(h)[:, None] - h / 2) / h
    t = WAKE_TIMES[k]
    centre = 0.6 * y * np.sin(2 * np.pi * (FREQ * t - 1.5 * x)) * 0.4
    field = np.sin(2 * np.pi * (3 * x - FREQ * t)) * np.exp(-((yy - centre) / 0.12) ** 2) * \
        np.clip(4 * x, 0, 1) * (0.4 + 0.6 * cl / 1.1)
    rgb = FIRE_ICE(0.5 + 0.5 * np.clip(field, -1, 1))[:, :, :3]
    return np.rint(rgb * 255).astype(np.uint8)


def write_data(folder, wakes: bool = True) -> Path:
    """Write the data into ``folder`` (see the module); returns ``folder``."""
    from PIL import Image
    folder = Path(folder)
    data = folder / "data"
    data.mkdir(parents=True, exist_ok=True)
    t = times()
    (data / "strips.csv").write_text("strip,station\n" + "".join(
        f"{k + 1},{s:.6f}\n" for k, s in enumerate(stations())))
    for case in CASES:
        table = np.column_stack([t, series(case, t)])
        np.savetxt(data / f"{case}_series.csv", table, delimiter=",", fmt="%.6f",
                   header="t,y_over_D,CL,CD", comments="")
        lift = sectional_lift(case, t)
        rows = "".join(f"{ti:.6f},{k + 1},{lift[i, k]:.6f}\n"
                       for i, ti in enumerate(t) for k in range(STRIPS))
        (data / f"{case}_lift.csv").write_text("time,strip,cl\n" + rows)
        if wakes:
            out = folder / "frames" / f"{case}_wake"
            out.mkdir(parents=True, exist_ok=True)
            for k in range(len(WAKE_TIMES)):
                Image.fromarray(wake(case, k)).save(out / f"frame_{k:05d}.png")
    return folder
