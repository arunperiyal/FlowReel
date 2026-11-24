"""A long case read through a window, and the whole span drawn stretched.

Usage: python run.py [DIR]   (default ./long_span_example)

Needs no data. It writes into DIR/case a FlexFlow-style case: a channel 200 long and
3 x 3 across, of bricks, whose floor is a wall zone (the body, 200 long), over ten
steps 0.1 apart in which the whole mesh rocks up and down by 0.2. DIR becomes a project
with the case as the tag ``channel`` (data/channel/domain.yml). Then:

1. The memory of one step read whole and read through shots/travel.yml's window.
2. shots/travel.yml: a window 20 long travels from station 20 to 180 with the camera; each
   frame reads only that part of the file (DIR/frames/travel/).
3. shots/whole.yml: the whole channel with its length drawn at a tenth (DIR/frames/whole/).
"""
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from tag_project import make_project  # noqa: E402

from flowreel.scene import render
from flowreel.scene.rendering import Scene
from flowreel.sources.plt.writer import write_plt

HERE = Path(__file__).parent
NX, NY, NZ, LENGTH = 800, 3, 3, 200.0
VARS = ["X", "Y", "Z", "U", "V", "W", "Pressure"]


def write_case(folder: Path) -> None:
    x = np.linspace(0, LENGTH, NX + 1)
    y = np.linspace(-1.5, 1.5, NY + 1)
    z = np.linspace(-1.5, 1.5, NZ + 1)
    zz, yy, xx = (a.ravel() for a in np.meshgrid(z, y, x, indexing="ij"))

    def node(i, j, k):
        return (k * (NY + 1) + j) * (NX + 1) + i

    bricks = np.array([[node(i, j, k), node(i + 1, j, k), node(i + 1, j + 1, k), node(i, j + 1, k),
                        node(i, j, k + 1), node(i + 1, j, k + 1), node(i + 1, j + 1, k + 1),
                        node(i, j + 1, k + 1)]
                       for k in range(NZ) for j in range(NY) for i in range(NX)])
    floor = np.array([[node(i, 0, k), node(i + 1, 0, k), node(i + 1, 0, k + 1), node(i, 0, k + 1)]
                      for k in range(NZ) for i in range(NX)])
    folder.mkdir(parents=True, exist_ok=True)
    for step in range(10):
        lift = 0.2 * np.sin(2 * np.pi * step / 10)
        u = 1 + np.sin(2 * np.pi * xx / 40 - step) * (1 - (yy / 1.5) ** 2)
        cols = [xx, yy + lift, zz, u, 0 * xx, 0 * xx, 0 * xx]
        write_plt(folder / f"channel.{step}.plt", VARS, cols,
                  [("fluid", 5, bricks), ("floor", 3, floor)], time=0.1 * step)


def main(folder: Path) -> None:
    write_case(folder / "case")
    make_project(folder, "channel", HERE / "data" / "channel" / "domain.yml")
    (folder / "shots").mkdir(exist_ok=True)
    shutil.copy(HERE / "cameras.yml", folder / "cameras.yml")
    for name in ("travel.yml", "whole.yml"):
        shutil.copy(HERE / "shots" / name, folder / "shots" / name)
    travel = Scene.make(folder / "shots" / "travel.yml")
    whole_gb = travel.source.memory_per_step(None)
    window_gb = travel.source.memory_per_step(travel.crop(0))
    print(f"one step read whole: {whole_gb * 1e3:.2f} MB; through the window: "
          f"{window_gb * 1e3:.2f} MB ({whole_gb / window_gb:.0f} times less)")
    for i in (0, 5, 9):
        box = travel.crop(i)
        print(f"frame {i}: window x {box.lo[0]:.1f} to {box.hi[0]:.1f}, "
              f"{travel.data(i).flow.n_cells} cells read")
    for shot in ("travel.yml", "whole.yml"):
        report = render(folder / "shots" / shot, out=folder / "frames", jobs=2)
        print(f"{report.folder}: {report.count('rendered')} drawn (backend {report.backend})")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("long_span_example"))
