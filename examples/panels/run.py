"""Panels: time histories drawn to each frame's time, then tiled by a layout.

Usage: python run.py [DIR]   (default ./panels_example)

Needs no data. It writes generated histories into DIR/data (two cylinders' lift, drag
and motion, and a pendulum's swing, sampled every 0.2), then:

1. compare.yml: a series panel, three rows on one time axis (DIR/frames/compare/).
2. phase.yml: a phase panel, the pendulum's angle against the motion (DIR/frames/phase/).
3. board.yml: both tiled into one picture (DIR/frames/board/).
4. The panels again: nothing changed, so every frame is skipped.
5. rate_board.yml: the layout draws the panels itself, as the film will, at three
   output frames per flow frame with a freeze of six frames at flow frame 5. The
   compare panel is composed at the flow's rate (DIR/frames/rate_board/); the phase
   panel, marked rate: output, is drawn once per output frame (DIR/frames/phase_output/).

The panels' times fall between the samples (every 0.5 against 0.2), so the dots sit on
values interpolated between saved samples.
"""
import shutil
import sys
from pathlib import Path

import numpy as np

from flowreel import compose

HERE = Path(__file__).parent
FILES = ("flowreel.yml", "style.yml", "compare.yml", "phase.yml", "board.yml", "rate_board.yml")


def write_data(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    t = np.round(np.arange(0, 8.001, 0.2), 6)
    w = 2 * np.pi * 0.4
    cases = {"bare": (0.6, 1.2, 0.5), "helical": (0.1, 0.9, 0.05)}
    for name, (cl, cd, y) in cases.items():
        grow = 1 - np.exp(-t / 2)
        force = np.c_[t, cl * grow * np.sin(w * t), cd + 0.1 * cl * grow * np.sin(2 * w * t)]
        np.savetxt(folder / f"{name}_force.csv", force, delimiter=",", header="time,CL,CD",
                   comments="", fmt="%.6g")
        motion = np.c_[t, y * grow * np.sin(w * t - 0.5)]
        np.savetxt(folder / f"{name}_motion.csv", motion, delimiter=",", header="time,y",
                   comments="", fmt="%.6g")
    swing = np.c_[t, 0.3 * (1 - np.exp(-t / 2)) * np.sin(w * t - 1.2)]
    np.savetxt(folder / "pendulum.csv", swing, delimiter=",", header="time,angle",
               comments="", fmt="%.6g")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy(HERE / name, folder / name)
    write_data(folder / "data")
    frames = folder / "frames"
    for name in ("compare.yml", "phase.yml"):
        report = compose.panel(folder / name, frames, jobs=2)
        print(f"{report.folder.name}: {report.count('drawn')} drawn")
    report = compose.layout(folder / "board.yml", frames)
    print(f"{report.folder.name}: {report.count('composed')} composed")
    for name in ("compare.yml", "phase.yml"):
        report = compose.panel(folder / name, frames, jobs=2)
        print(f"{report.folder.name}: {report.count('skipped')} skipped")
    output = compose.output_positions(16, per_frame=3, holds=[(5, 6)])
    report = compose.layout(folder / "rate_board.yml", frames, output=output)
    print(f"{report.folder.name}: {report.count('composed')} composed")
    for tile, panel in report.overlays:
        print(f"{panel.folder.name}: {panel.count('drawn')} drawn at {tile.at}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("panels_example"))
