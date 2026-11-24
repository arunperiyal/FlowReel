"""Declare bodies, measure them, and follow one along its span.

Usage: python run.py [DIR]   (default ./bodies_example)

Needs no data. It writes into DIR/case a riser 40 diameters long, bent to
y = 1.5 sin(pi x / 40), a ball beside it and a small flow box (VTK files), and the
riser's displacement at five probe nodes as FlexFlow Analyzer exports it (one CSV per
node, ``tsId, time, aleDisp_y``) into DIR/data/bent/series. The flow is ten tiny steps
0.1 apart, so the second shot has a time to follow. Then:

1. ``data import vtk`` makes the case the tag ``bent`` and measures every surface: axis
   and diameter measured, supports left to fill. Its domain.yml is printed.
2. The hand-edited data/bent/domain.yml of this folder names the surfaces ``riser`` and
   ``ball`` and fills in the riser's supports; it replaces what the import wrote (the
   measured block stays).
3. The riser's declared displacement series is read by body name, the five nodes as
   one history with their stations.
4. shots/riser_travel.yml follows ``riser`` along its span; the focal point of each
   frame is printed, on the bend, and the frames go to DIR/frames/riser_travel/.
5. shots/span.yml draws the whole riser from its probes: centreline, rest line, envelope,
   supports and an arrow driven by a series track, into DIR/frames/riser_span/.
6. shots/pendulum.yml draws the virtual pendulum hung from the riser at mid-span, swung
   by series/pendulum.csv (``pendDisp``, radians), as a ghost; the bob's lowest point of
   each frame is printed (the pivot's height less ``4 cos(angle) + 0.6``).
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

sys.path.insert(0, str(Path(__file__).parent.parent))
from tag_project import make_project  # noqa: E402

from flowreel.project.domain import find_tag  # noqa: E402
from flowreel.scene import render  # noqa: E402
from flowreel.scene.rendering import Scene  # noqa: E402

HERE = Path(__file__).parent
LENGTH, BEND = 40.0, 1.5


def riser(rings=161, sides=32) -> pv.PolyData:
    """A tube of diameter 1 along x from 0 to LENGTH, its axis bent in y."""
    x = np.linspace(0, LENGTH, rings)
    theta = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    xx, tt = np.meshgrid(x, theta, indexing="ij")
    pts = np.column_stack([xx.ravel(), 0.5 * np.cos(tt.ravel()), 0.5 * np.sin(tt.ravel())])
    pts[:, 1] += BEND * np.sin(np.pi * pts[:, 0] / LENGTH)
    i, j = np.meshgrid(np.arange(rings - 1), np.arange(sides), indexing="ij")
    a, b = i * sides + j, i * sides + (j + 1) % sides
    quads = np.column_stack([np.full(a.size, 4), a.ravel(), b.ravel(), b.ravel() + sides,
                             a.ravel() + sides])
    return pv.PolyData(pts, quads.ravel())


def write_data(folder: Path) -> None:
    data = folder / "case"
    series = folder / "data" / "bent" / "series"
    data.mkdir(parents=True, exist_ok=True)
    series.mkdir(parents=True, exist_ok=True)
    riser().save(data / "cyl.vtp")
    pv.Sphere(radius=0.6, center=(25, -0.5, 2.5)).save(data / "ball.vtp")
    box = pv.ImageData(dimensions=(9, 5, 5), spacing=(5, 1.5, 1), origin=(0, -3, -2))
    for name in ("U", "V", "W"):
        box.point_data[name] = np.zeros(box.n_points, dtype=np.float32)
    box["U"][:] = 1.0
    for step in range(10):
        box.save(data / f"flow_{step}.vti")
    times = np.arange(1, 11) * 0.1
    for node, x in enumerate(np.linspace(0, LENGTH, 5)):
        dy = BEND * np.sin(np.pi * x / LENGTH) * np.sin(2 * np.pi * times)
        rows = "".join(f"{i + 1},{t:.12g},{d:.12g}\n" for i, (t, d) in enumerate(zip(times, dy)))
        (series / f"riser_disp_{node}.csv").write_text("tsId,time,aleDisp_y\n" + rows)
    angle = 0.6 * np.sin(2 * np.pi * times)
    (series / "pendulum.csv").write_text("time,pendDisp\n0,0\n" + "".join(
        f"{t:.12g},{a:.12g}\n" for t, a in zip(times, angle)))


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    write_data(folder)
    make_project(folder, "bent", HERE / "data" / "bent" / "domain.yml", kind="vtk",
                 flags=("--flow", "flow_*.vti", "--body", "cyl=case/cyl.vtp",
                        "--body", "ball=case/ball.vtp"), echo=True)
    (folder / "shots").mkdir(exist_ok=True)
    for name in ("riser_travel.yml", "span.yml", "pendulum.yml"):
        shutil.copy(HERE / "shots" / name, folder / "shots" / name)
    shutil.copy(HERE / "cameras.yml", folder / "cameras.yml")
    print("declared:", ", ".join(f"{b.name} (zone {b.zone})"
                                 for b in find_tag(folder, "bent").bodies.values()))
    scene = Scene.make(folder / "shots" / "riser_travel.yml")
    disp = scene.source.series("displacement", body="riser")
    at = disp[np.isclose(disp.time, 0.3)]
    print(f"displacement: {len(disp)} rows, nodes {sorted(int(n) for n in disp.node.unique())}; "
          "dy at t = 0.3 by station: " + ", ".join(f"{s:g}: {d:.3f}" for s, d in
                                                     zip(at.station, at.dy)))
    for i in (0, 6, 11):
        x, y, z = scene.camera.view(i, scene.data(i)).focal
        print(f"frame {i:2d}: focal ({x:.2f}, {y:.3f}, {z:.3f}); "
              f"bend there {BEND * np.sin(np.pi * x / LENGTH):.3f}")
    for shot in ("riser_travel.yml", "span.yml", "pendulum.yml"):
        report = render(folder / "shots" / shot, out=folder / "frames", jobs=2)
        print(f"{report.folder}: {report.count('rendered')} drawn, "
              f"{report.count('skipped')} skipped (backend {report.backend})")
    span = Scene.make(folder / "shots" / "span.yml")
    arrow = [span.values(i)[2]["length"] for i in range(span.plan.n_frames)]
    print("arrow length by frame: " + ", ".join(f"{a:.3f}" for a in arrow))
    pend = Scene.make(folder / "shots" / "pendulum.yml")
    low = [float(pend.data(i).body("pendulum").points[:, 1].min()) for i in range(pend.plan.n_frames)]
    print("bob's lowest point by frame: " + ", ".join(f"{y:.3f}" for y in low))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bodies_example"))
