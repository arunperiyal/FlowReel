"""Panels: time histories drawn to each frame's time, tiled in a scene.

Usage: python run.py [DIR]   (default ./panels_example)

Needs no data. It makes DIR a project, and writes generated histories into
DIR/data/cases/series (two cylinders' lift, drag and motion, and a pendulum's swing,
sampled every 0.2); data/cases/domain.yml declares them as the bodies ``bare``,
``helical`` and ``pendulum`` of the tag ``cases``. Then:

1. panels/compare.yml: a series panel, three rows on one time axis (DIR/frames/compare/).
2. panels/phase.yml: a phase panel, the pendulum's angle against the motion
   (DIR/frames/phase/).
3. The panels again: nothing changed, so every frame is skipped.
4. layouts/board.yml, the scene ``board`` of film.yml: both panels in one picture. The
   build draws the panels itself, at their boxes' size and at the film's rate (6 frames
   a second: each time of a panel held for three frames), with a freeze of a second at
   2.5 s. ``film lengths`` plans it; ``scene preview`` draws stills (DIR/frames/scenes/board/).

The panels' times fall between the samples (every 0.5 against 0.2), so the dots sit on
values interpolated between saved samples.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


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
    def flowreel(*args: str) -> str:
        """The command's output, paths from DIR and without its timings."""
        done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder,
                              capture_output=True, text=True)
        if done.returncode:
            raise SystemExit(done.stderr or done.stdout)
        return re.sub(r" in [\d.]+ s", "", done.stdout.strip().replace(f"{folder}/", ""))

    folder.mkdir(parents=True, exist_ok=True)
    flowreel("project", "init", "--force")
    for sub in ("panels", "layouts", "data"):
        shutil.copytree(HERE / sub, folder / sub, dirs_exist_ok=True)
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    write_data(folder / "data" / "cases" / "series")
    for jobs in ("2", "1"):                      # the second pass skips every frame
        for name in ("compare", "phase"):
            print(flowreel("panel", "draw", f"panels/{name}.yml", "-j", jobs).splitlines()[-1])
    print(flowreel("film", "lengths"))
    print(flowreel("scene", "preview", "board", "--at", "1", "3", "6").splitlines()[-1])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("panels_example"))
