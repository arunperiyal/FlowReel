"""Panels of the generated riser case: a span map and a locator, tiled.

Usage: python panels.py [DIR]   (default ./riser500_panels)

Needs no data: riser500_case.py writes the case into DIR. Then, with the frame times of
travel.yml (eight frames, 0 to 3.5):

1. span_map.yml: the 51 probes' displacement against span and time, filling in
   (DIR/frames/span_map/).
2. locator.yml: the riser as a bar, its shape 100 times larger, its pinned and roller
   ends, and travel.yml's window moving from station 20 to 480 (DIR/frames/locator/).
3. panel_board.yml: the locator over the map (DIR/frames/panel_board/).

No flow field is read: the panels read the probes' CSV files and the shot's crop.
"""
import shutil
import sys
from pathlib import Path

from flowreel import compose

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import riser500_case as case  # noqa: E402

FILES = ("span_map.yml", "locator.yml", "panel_board.yml")


def main(folder: Path) -> None:
    case.write_case(folder)
    for name in FILES:
        shutil.copy(HERE / name, folder / name)
    for name in ("span_map.yml", "locator.yml"):
        report = compose.panel(folder / name, folder / "frames", jobs=2)
        print(f"{report.folder.name}: {report.count('drawn')} drawn")
    report = compose.layout(folder / "panel_board.yml", folder / "frames")
    print(f"{report.folder.name}: {report.count('composed')} composed")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("riser500_panels"))
