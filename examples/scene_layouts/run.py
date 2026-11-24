"""Layouts: frame folders tiled into one picture, and one shot at several stations.

Usage: python run.py [DIR]   (default ./compose_layout_example)

Needs no data. It draws three small frame folders with PIL (DIR/frames/bare and
DIR/frames/helical, eight frames of a moving dot; DIR/frames/title, one frame), then:

1. compare.yml: bare and helical side by side, labelled (DIR/frames/compare/).
2. grid.yml: four tiles on a 2 x 2 grid; the one-frame title is held (DIR/frames/grid/).
3. Both again: nothing changed, so every frame is skipped.
4. stations.yml: window.yml, a window round the floor of a generated channel 200 long,
   rendered at stations 40, 100 and 160 and tiled in a row (DIR/frames/stations/).
   This step draws with VTK off screen.
"""
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from flowreel import compose
from flowreel.sources.plt.writer import write_plt

HERE = Path(__file__).parent
FILES = ("compare.yml", "grid.yml", "window.yml", "stations.yml", "cameras.yml", "flowreel.yml")


def draw_frames(folder: Path, colour: str, wobble: float, n: int = 8) -> None:
    """``n`` frames of a dot going round, 480 x 270."""
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        im = Image.new("RGB", (480, 270), "#1b2630")
        d = ImageDraw.Draw(im)
        x = 240 + 150 * math.cos(2 * math.pi * i / n)
        y = 135 + wobble * math.sin(2 * math.pi * i / n)
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=colour)
        im.save(folder / f"frame_{i:05d}.png")


def write_case(folder: Path, nx: int = 400, length: float = 200.0) -> None:
    """A channel ``length`` long, 3 x 3 across, of bricks, its floor a wall zone; four
    steps in which the flow's waves travel along x."""
    x = np.linspace(0, length, nx + 1)
    y = np.linspace(-1.5, 1.5, 4)
    z = np.linspace(-1.5, 1.5, 4)
    zz, yy, xx = (a.ravel() for a in np.meshgrid(z, y, x, indexing="ij"))

    def node(i, j, k):
        return (k * 4 + j) * (nx + 1) + i

    bricks = np.array([[node(i, j, k), node(i + 1, j, k), node(i + 1, j + 1, k), node(i, j + 1, k),
                        node(i, j, k + 1), node(i + 1, j, k + 1), node(i + 1, j + 1, k + 1),
                        node(i, j + 1, k + 1)]
                       for k in range(3) for j in range(3) for i in range(nx)])
    floor = np.array([[node(i, 0, k), node(i + 1, 0, k), node(i + 1, 0, k + 1), node(i, 0, k + 1)]
                      for k in range(3) for i in range(nx)])
    folder.mkdir(parents=True, exist_ok=True)
    for step in range(4):
        u = 1 + np.sin(2 * np.pi * xx / 45 - step) * (1 - (yy / 1.5) ** 2)
        write_plt(folder / f"channel.{step}.plt", ["X", "Y", "Z", "U", "V", "W", "Pressure"],
                  [xx, yy, zz, u, 0 * xx, 0 * xx, 0 * xx],
                  [("fluid", 5, bricks), ("floor", 3, floor)], time=0.1 * step)


def say(report) -> None:
    print(f"{report.folder.name}: {report.count('composed')} composed, "
          f"{report.count('skipped')} skipped, {report.size[0]} x {report.size[1]}")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy(HERE / name, folder / name)
    frames = folder / "frames"
    draw_frames(frames / "bare", "#e8b04a", 80)
    draw_frames(frames / "helical", "#6ac1c8", 10)
    draw_frames(frames / "title", "#ffffff", 0, n=1)
    for name in ("compare.yml", "grid.yml"):
        say(compose.layout(folder / name, frames))
    for name in ("compare.yml", "grid.yml"):
        say(compose.layout(folder / name, frames))
    write_case(folder / "case")
    say(compose.layout(folder / "stations.yml", frames, render={"jobs": 2}))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("compose_layout_example"))
