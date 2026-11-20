"""A film project on generated data: a card, a layout shot with live plots and a
freeze, a hold of its last frame, a watermark of text; silent.

Usage: python run.py [DIR]   (default ./film_project_example)

Needs no data, only ffmpeg. The comparison example's case_data.py writes two generated
cases into DIR (their series as CSV and stand-in wake frames); its flowreel.yml,
compare.yml and plots.yml are copied beside this example's film.yml and card.yml. The
build composes the comparison at its own rate without the plots, draws the plots once
per output frame (freeze included) and lays them on the interpolated wakes, then joins
the clips into DIR/film.mp4. Prints the build's report, paths relative to DIR.

In the shell, the same project is built with ``use project:DIR`` and ``film build``.
"""
import shutil
import sys
from pathlib import Path

from flowreel.film.build import build

HERE = Path(__file__).parent
COMPARE = HERE.parent / "compare"
sys.path.insert(0, str(COMPARE))
import case_data  # noqa: E402

FILES = {COMPARE: ("flowreel.yml", "compare.yml", "plots.yml"), HERE: ("film.yml", "card.yml")}


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "data").is_dir():      # written once: new frames would rebuild clips
        case_data.write_data(folder)
    for source, names in FILES.items():
        for name in names:
            shutil.copy(source / name, folder / name)
    built = build(folder / "film.yml", panels={"jobs": 2})
    for line in built.table():
        print(line.replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_project_example"))
