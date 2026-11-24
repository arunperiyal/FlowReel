"""The comparison and the lift map of two generated cases, as scenes of a film.

Usage: python run.py [DIR]   (default ./compare_example)

Needs no data: case_data.py writes two cases' series (DIR/data/cases/series), their
sectional lift and stand-in wake frames (DIR/frames/) into a project at DIR; the tag
``cases`` (data/cases/domain.yml) declares the series as the bodies ``bare`` and ``helical``.
Then, as the AFMS film did with the prototype's scripts:

1. ``film lengths``: the film's plan, ``compare`` (the wakes stacked on the left, the live
   plots of panels/plots.yml on the right, a freeze of a second at wake frame 15) and
   ``liftmap`` (panels/liftmap.yml, the sectional lift of both cases against span and
   time, filling in from the left).
2. ``scene preview``: a still of each scene (DIR/frames/scenes/). The build draws the
   plots itself, once per output frame, and lays them on the interpolated wakes.

tests/test_golden_compose.py checks frame 15 of the comparison and frame 20 of the lift
map against frames drawn by the prototype's own code.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import case_data  # noqa: E402


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
    case_data.write_data(folder, data=folder / "data" / "cases" / "series")
    print(flowreel("film", "lengths"))
    print(flowreel("scene", "preview", "compare", "--at", "1", "3.9", "5").splitlines()[-1])
    print(flowreel("scene", "preview", "liftmap", "--at", "1", "6").splitlines()[-1])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("compare_example"))
