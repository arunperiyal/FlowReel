"""A film project on generated data: a title, a comparison with live plots and a freeze,
a hold of its last frame, a watermark of text; silent.

Usage: python run.py [DIR]   (default ./film_project_example)

Needs no data, only ffmpeg. The comparison example's case_data.py writes two generated
cases into a project at DIR (their series as CSV under the tag ``cases``, and stand-in wake
frames); its data/ and panels/ are copied beside this example's film.yml and
layouts/compare.yml. The build draws the plots once per output frame (freeze included)
and lays them on the interpolated wakes, then joins the clips into DIR/film.mp4. Prints
the build's report, paths relative to DIR.

In the shell, the same project is built with ``use project:DIR`` and ``film build``.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
COMPARE = HERE.parent / "compare"
sys.path.insert(0, str(COMPARE))
sys.path.insert(0, str(HERE.parent))
import case_data  # noqa: E402
from tag_project import flowreel  # noqa: E402


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "flowreel.yml").is_file():
        flowreel(folder, "project", "init", "--force")
    if not (folder / "frames").is_dir():      # written once: new frames would rebuild clips
        case_data.write_data(folder, data=folder / "data" / "cases" / "series")
    for sub in ("data", "panels"):
        shutil.copytree(COMPARE / sub, folder / sub, dirs_exist_ok=True)
    shutil.copytree(HERE / "layouts", folder / "layouts", dirs_exist_ok=True)
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    built = flowreel(folder, "film", "build", "-j", "2")
    for line in built.splitlines():
        line = re.sub(r" in [\d.]+ s", "", line)
        if not line.startswith("built"):
            print(line.replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_project_example"))
