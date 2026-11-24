"""Write a generated case of a moving cylinder in a ring of flow, for the flow panels.

Needs no data and no solver: everything is made from formulas, at test time or when
``run.py`` asks, and never checked in. Lengths are in diameters (D = 1).

``write_case(folder)`` writes ``case/cyl.<step>.plt``, ``STEPS`` steps ``DT`` apart
(steps 0, 10, 20, ...). The volume zone ``fluid`` is a ring of bricks around a cylinder
of radius ``RADIUS`` along x, from 0 to ``SPAN``, out to radius ``OUTER``; the wall zone
``cyl`` is the ring's inner face, sharing its nodes, so wall fields are sampled on the
wall itself. The whole mesh moves across the flow, ``y = SPEED t``, as a body that
vibrates would over a short time.

The flow is made so that every panel's numbers are known exactly:

- ``U = SHEAR z``: the wall shear along x is ``mu SHEAR sin(theta)``, so it is zero
  where the wall crosses ``z = 0`` (the strip's zero contour);
- ``V = SPEED - OMEGA z``, ``W = OMEGA (y - SPEED t)``: the body's own velocity plus a
  solid rotation about its axis, so the flow seen from the body turns in circles round
  it and the spanwise vorticity is ``2 OMEGA`` everywhere;
- ``p = SLOPE z``.

``make_project`` builds a project on tags from it; ``write_case`` alone writes only the
PLT files, and with ``project=True`` also a ``flowreel.yml`` of the layout before tags.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from flowreel.sources.plt.writer import write_plt

HERE = Path(__file__).parent
RADIUS = 0.5
OUTER = 3.0
SPAN = 4.0
STEPS = 4
DT = 0.5
SPEED = 0.2           # the body's velocity in y
OMEGA = 0.8           # rotation of the flow about the body's axis
SHEAR = 0.6           # dU/dz
SLOPE = 1.0           # dp/dz
RINGS = 14            # nodes from the wall out
AROUND = 48           # nodes round the body
PLANES = 9            # nodes along the span
VARS = ["X", "Y", "Z", "U", "V", "W", "Pressure"]


def centre_y(t):
    """The body's centre in y at time ``t``."""
    return SPEED * np.asarray(t, dtype=float)


def _mesh():
    """Rest nodes ``(x, r, theta)`` and the brick and wall-quad connectivity."""
    r = RADIUS + (OUTER - RADIUS) * np.linspace(0, 1, RINGS) ** 1.5
    theta = np.linspace(0, 2 * np.pi, AROUND, endpoint=False)
    x = np.linspace(0, SPAN, PLANES)
    xx, rr, tt = (a.ravel() for a in np.meshgrid(x, r, theta, indexing="ij"))

    def node(k, i, j):
        return (k * RINGS + i) * AROUND + j % AROUND

    k, i, j = (a.ravel() for a in np.meshgrid(np.arange(PLANES - 1), np.arange(RINGS - 1),
                                              np.arange(AROUND), indexing="ij"))
    bricks = np.column_stack([node(k, i, j), node(k, i + 1, j), node(k, i + 1, j + 1),
                              node(k, i, j + 1), node(k + 1, i, j), node(k + 1, i + 1, j),
                              node(k + 1, i + 1, j + 1), node(k + 1, i, j + 1)])
    k, j = (a.ravel() for a in np.meshgrid(np.arange(PLANES - 1), np.arange(AROUND), indexing="ij"))
    wall = np.column_stack([node(k, 0, j), node(k, 0, j + 1), node(k + 1, 0, j + 1),
                            node(k + 1, 0, j)])
    return (xx, rr, tt), bricks, wall


# The project file of a case before tags (bodies and reference in flowreel.yml), which the
# unit tests of the panels still read; phase 10's last branch removes it with that layout.
BEFORE_TAGS = """bodies:
  cylinder: {zone: cyl, axis: x, diameter: 1.0,
             ends: [{at: 0.0, support: clamped}, {at: 4.0, support: clamped}]}
reference: {rho: 1.0, u_inf: 1.0}
"""


def write_case(folder, steps: int = STEPS, project: bool = True) -> Path:
    """Write the case into ``folder`` (see the module); returns ``folder``."""
    folder = Path(folder)
    case = folder / "case"
    case.mkdir(parents=True, exist_ok=True)
    (x, r, theta), bricks, wall = _mesh()
    for k in range(steps):
        t = k * DT
        y = centre_y(t) + r * np.cos(theta)
        z = r * np.sin(theta)
        u = SHEAR * z
        v = SPEED - OMEGA * z
        w = OMEGA * (y - centre_y(t))
        p = SLOPE * z
        write_plt(case / f"cyl.{10 * k}.plt", VARS, [x, y, z, u, v, w, p],
                  [("fluid", 5, bricks), ("cyl", 3, wall)], time=t)
    if project:
        (folder / "flowreel.yml").write_text(BEFORE_TAGS)
    return folder


UNITS_AND_BODY = """units:                           # the generated flow is in units of its own: q = 1/2
  rho: 1.0
  mu: 1.0
  u_inf: 1.0
bodies:
  cylinder:
    zone: cyl
    axis: x
    diameter: 1.0
    ends:
      - {at: 0.0, support: clamped}
      - {at: 4.0, support: clamped}
"""


def flowreel(folder: Path, *args: str) -> str:
    """Run ``flowreel ARGS`` in ``folder``; stop with its message if it fails."""
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder,
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(done.stderr or done.stdout)
    return done.stdout


def make_project(folder, tag: str = "cylinder", steps: int = STEPS) -> Path:
    """A project in ``folder`` with the generated case as the tag ``tag``: the case written
    to ``folder/case``, linked by ``data import plt``, its units and its body (the wall
    zone ``cyl`` as ``cylinder``, held at both ends) filled in as a person would. Returns
    the tag's ``domain.yml``."""
    folder = Path(folder)
    write_case(folder, steps=steps, project=False)
    flowreel(folder, "project", "init", "--force")
    flowreel(folder, "data", "import", "plt", "--path", "case", "--tag", tag)
    path = folder / "data" / tag / "domain.yml"
    text = path.read_text()
    start, end = text.index("units:"), text.index("\nmeasured:") + 1
    path.write_text(text[:start] + UNITS_AND_BODY + text[end:])
    return path
