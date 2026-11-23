"""Panels drawn from flow data: a section, cuts along the span and a strip, tiled.

Usage: python run.py [DIR]   (default ./flow_panels_example)

Needs no data: cylinder_case.py writes a generated case into DIR (a cylinder 4
diameters long moving across a ring of flow, four steps 0.5 apart). Then:

1. section.yml: the cut at mid-span, the flow seen from the moving body and a close
   view of the wall above it (DIR/frames/section/).
2. cuts.yml: the same cut at three stations side by side (DIR/frames/cuts/).
3. strip.yml: the body seen from +y, coloured by the wall shear along the span, with
   the line where it is zero (DIR/frames/strip/).
4. board.yml: the three tiled into one picture (DIR/frames/board/).
5. ``flowreel project sections``: the force on 8 sections along the body at every step,
   from the flow (series/cylinder_sections.csv, declared in flowreel.yml), and
   liftmap.yml, a map of it against the span and time (DIR/frames/liftmap/).
"""
import shutil
import subprocess
import sys
from pathlib import Path

from flowreel import compose

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import cylinder_case as case  # noqa: E402

PANELS = ("section.yml", "cuts.yml", "strip.yml")


def main(folder: Path) -> None:
    case.write_case(folder)
    for name in PANELS + ("board.yml",):
        shutil.copy(HERE / name, folder / name)
    for name in PANELS:
        report = compose.panel(folder / name, folder / "frames", jobs=2)
        print(f"{report.folder.name}: {report.count('drawn')} drawn")
    report = compose.layout(folder / "board.yml", folder / "frames")
    print(f"{report.folder.name}: {report.count('composed')} composed")
    subprocess.run([sys.executable, "-m", "flowreel", "project", "sections", "plt:case",
                    "--param", "mu=0.5", "--sections", "8"], cwd=folder, check=True,
                   capture_output=True)
    print("sections: series/cylinder_sections.csv")
    shutil.copy(HERE / "liftmap.yml", folder / "liftmap.yml")
    report = compose.panel(folder / "liftmap.yml", folder / "frames")
    print(f"{report.folder.name}: {report.count('drawn')} drawn")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("flow_panels_example"))
