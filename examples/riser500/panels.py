"""Panels of the generated riser case: a span map and a locator, tiled in a scene.

Usage: python panels.py [DIR]   (default ./riser500_panels)

Needs no data: riser500_case.py writes the case into DIR and makes it a project (the tag
``riser``). Then, with the frame times of shots/travel.yml (eight frames, 0 to 3.5):

1. panels/span_map.yml: the 51 probes' displacement against span and time, filling in
   (DIR/frames/span_map/).
2. panels/locator.yml: the riser as a bar, its shape 100 times larger, its pinned and
   roller ends, and travel.yml's window moving from station 20 to 480
   (DIR/frames/locator/).
3. layouts/board.yml, the scene ``board`` of film.yml: the locator over the map
   (``scene preview``, DIR/frames/scenes/board/).

No flow field is read: the panels read the probes' CSV files and the shot's crop.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import riser500_case as case  # noqa: E402
from tag_project import flowreel  # noqa: E402


def main(folder: Path) -> None:
    case.make_project(case.write_case(folder))

    def run(*args: str) -> str:
        out = flowreel(folder, *args).strip().splitlines()[-1].replace(f"{folder}/", "")
        return re.sub(r" in [\d.]+ s", "", out)

    for name in ("span_map", "locator"):
        print(run("panel", "draw", f"panels/{name}.yml", "-j", "2"))
    print(run("scene", "preview", "board", "--at", "2"))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("riser500_panels"))
