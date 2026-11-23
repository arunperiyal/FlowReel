"""Write a generated case of a riser 500 diameters long (plan Section 19.3, branch 9).

Needs no data and no solver: everything is made from formulas, at test time or when
``run.py`` asks, and never checked in. Lengths are in diameters (D = 1).

``write_case(folder)`` writes:

- ``case/riser.<step>.plt``: a FlexFlow-style PLT per step, ``steps`` steps ``DT``
  apart. The volume zone ``fluid`` is a channel ``length`` long and 8 x 8 across, of
  bricks 0.5 long; the wall zones are ``cyl``, a tube of diameter 1 along x from 0 to
  ``length`` on the channel's axis, and ``cyl2``, a second cylinder 12 long, still,
  beside the first (z = 2.5, x 100 to 112). The riser vibrates across the flow in its
  third mode: ``y = AMP sin(3 pi x / length) sin(2 pi t / PERIOD)``. The flow is a wake
  that follows the riser, so a slice shows it.
- ``data/riser_disp_<node>.csv``: the riser's displacement at ``PROBES`` probe nodes, 0
  to ``length``, as FlexFlow Analyzer exports it (``tsId, time, aleDisp_y``), sampled
  every ``DT / 5``; ``data/riser_nodes.csv`` (``node, station``) says where each is.
- ``data/pendulum.csv``: the swing of a pendulum hung from the riser at mid-span
  (``time, pendDisp``, radians), ``SWING sin(2 pi t / PERIOD)``.

The project file and the shots that read it are beside this module (``flowreel.yml``,
``travel.yml``, ``span.yml``, ``pendulum.yml``, ``cameras.yml``); ``write_case`` copies
them into ``folder`` unless ``project=False`` (they are for the 500-long case).

Sizes: a channel 500 long has 1000 x 8 x 8 bricks and a riser of 2001 rings, about 4 MB
a step; it is coarse across the flow, so that the suite stays fast, and long, so that a
window reads a small part of it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from flowreel.sources.plt.writer import write_plt

HERE = Path(__file__).parent
LENGTH = 500.0
STEPS = 8
DT = 0.5
PERIOD = 4.0
AMP = 0.6             # largest displacement of the riser, D
SWING = 0.5           # largest swing of the pendulum, radians
PROBES = 51
CELL = 0.5            # brick length along the span
HALF = 4.0            # half-width of the channel
ACROSS = 8            # bricks across, in y and in z
RINGS_PER_D = 4       # riser rings per diameter
SIDES = 16
VARS = ["X", "Y", "Z", "U", "V", "W", "Pressure"]
FILES = ("flowreel.yml", "cameras.yml", "travel.yml", "span.yml", "pendulum.yml")


def displacement(x, t, length: float = LENGTH):
    """The riser's displacement in y at stations ``x`` and time ``t``."""
    return AMP * np.sin(3 * np.pi * np.asarray(x) / length) * np.sin(2 * np.pi * t / PERIOD)


def swing(t):
    """The pendulum's angle in radians at time ``t``."""
    return SWING * np.sin(2 * np.pi * np.asarray(t) / PERIOD)


def _channel(length: float):
    nx = int(round(length / CELL))
    x = np.linspace(0, length, nx + 1)
    yz = np.linspace(-HALF, HALF, ACROSS + 1)
    zz, yy, xx = (a.ravel() for a in np.meshgrid(yz, yz, x, indexing="ij"))
    i, j, k = (a.ravel() for a in np.meshgrid(np.arange(nx), np.arange(ACROSS),
                                              np.arange(ACROSS), indexing="ij"))

    def node(i, j, k):
        return (k * (ACROSS + 1) + j) * (nx + 1) + i

    bricks = np.column_stack([node(i, j, k), node(i + 1, j, k), node(i + 1, j + 1, k),
                              node(i, j + 1, k), node(i, j, k + 1), node(i + 1, j, k + 1),
                              node(i + 1, j + 1, k + 1), node(i, j + 1, k + 1)])
    return np.column_stack([xx, yy, zz]), bricks


def _tube(x0: float, x1: float, centre_y: float, centre_z: float, rings: int):
    x = np.linspace(x0, x1, rings)
    theta = np.linspace(0, 2 * np.pi, SIDES, endpoint=False)
    xx, tt = (a.ravel() for a in np.meshgrid(x, theta, indexing="ij"))
    points = np.column_stack([xx, centre_y + 0.5 * np.cos(tt), centre_z + 0.5 * np.sin(tt)])
    r, s = (a.ravel() for a in np.meshgrid(np.arange(rings - 1), np.arange(SIDES), indexing="ij"))
    a, b = r * SIDES + s, r * SIDES + (s + 1) % SIDES
    return points, np.column_stack([a, b, b + SIDES, a + SIDES])


def write_case(folder, length: float = LENGTH, steps: int = STEPS, project: bool = True) -> Path:
    """Write the case into ``folder`` (see the module); returns ``folder``."""
    folder = Path(folder)
    case, data = folder / "case", folder / "data"
    case.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    fluid, bricks = _channel(length)
    riser, riser_quads = _tube(0.0, length, 0.0, 0.0, int(length * RINGS_PER_D) + 1)
    other, other_quads = _tube(100.0, 112.0, 0.0, 2.5, 12 * RINGS_PER_D + 1)
    n_fluid, n_riser = len(fluid), len(riser)
    zones = [("fluid", 5, bricks), ("cyl", 3, riser_quads + n_fluid),
             ("cyl2", 3, other_quads + n_fluid + n_riser)]
    for step in range(steps):
        t = step * DT
        moved = riser.copy()
        moved[:, 1] += displacement(moved[:, 0], t, length)
        points = np.vstack([fluid, moved, other])
        x, y, z = points.T
        centre = displacement(x, t, length)
        r2 = (y - centre) ** 2 + z ** 2
        wake = np.exp(-r2 / 2.0) * (0.7 + 0.3 * np.sin(2 * np.pi * (x / 6 - t / PERIOD)))
        u = 1.0 - wake
        v = 0.4 * np.exp(-r2 / 2.0) * np.cos(2 * np.pi * (x / 6 - t / PERIOD))
        w = np.zeros_like(x)
        p = 0.5 * (1 - u ** 2)
        write_plt(case / f"riser.{step}.plt", VARS, [x, y, z, u, v, w, p], zones, time=t)
    times = np.arange(0, (steps - 1) * DT + 1e-9, DT / 5)
    stations = np.linspace(0, length, PROBES)
    (data / "riser_nodes.csv").write_text("node,station\n" + "".join(
        f"{n},{s:.12g}\n" for n, s in enumerate(stations)))
    for node, s in enumerate(stations):
        dy = displacement(s, times, length)
        (data / f"riser_disp_{node}.csv").write_text("tsId,time,aleDisp_y\n" + "".join(
            f"{i + 1},{t:.12g},{d:.12g}\n" for i, (t, d) in enumerate(zip(times, dy))))
    (data / "pendulum.csv").write_text("time,pendDisp\n" + "".join(
        f"{t:.12g},{a:.12g}\n" for t, a in zip(times, swing(times))))
    if project:
        for name in FILES:
            shutil.copy(HERE / name, folder / name)
    return folder
