"""Panels drawn from flow data: a section, cuts along the span and a strip, tiled.

Usage: python run.py [DIR]   (default ./flow_panels_example)

Needs no data: cylinder_case.py writes a generated case into DIR/case (a cylinder 4
diameters long moving across a ring of flow, four steps 0.5 apart) and imports it as the
tag ``cylinder`` (units and body filled in, as in data/cylinder/domain.yml). Then:

1. panels/section.yml: the cut at mid-span, the flow seen from the moving body and a
   close view of the wall above it (DIR/frames/section/).
2. panels/cuts.yml: the same cut at three stations side by side (DIR/frames/cuts/).
3. panels/strip.yml: the body seen from +y, coloured by the wall shear along the span,
   with the line where it is zero (DIR/frames/strip/).
4. layouts/board.yml, the scene ``board`` of film.yml: the three tiled into one picture.
   ``scene preview`` draws it (DIR/frames/scenes/board/); the build would draw the same
   panels at their boxes' size.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import cylinder_case as case  # noqa: E402

PANELS = ("section", "cuts", "strip")


def report(out: str, folder: Path) -> str:
    """The command's last line, paths from ``folder``, and without its timing."""
    line = out.strip().splitlines()[-1].replace(f"{folder}/", "")
    return re.sub(r" in [\d.]+ s", "", line)


def main(folder: Path) -> None:
    case.make_project(folder)
    for sub in ("panels", "layouts"):
        shutil.copytree(HERE / sub, folder / sub, dirs_exist_ok=True)
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    for name in PANELS:
        out = case.flowreel(folder, "panel", "draw", f"panels/{name}.yml", "-j", "2")
        print(report(out, folder))
    print(report(case.flowreel(folder, "scene", "preview", "board", "--at", "0.5"), folder))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("flow_panels_example"))
