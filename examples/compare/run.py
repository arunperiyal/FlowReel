"""The comparison and the lift map of two generated cases, composed from files.

Usage: python run.py [DIR]   (default ./compare_example)

Needs no data: case_data.py writes two cases' series, their sectional lift and stand-in
wake frames into DIR. Then, as the AFMS film did with the prototype's scripts:

1. compare.yml: the two wakes stacked on the left and the live plots (plots.yml) on
   the right, composed into DIR/frames/compare/. The plots are a rate: output panel:
   here composed at the wakes' frames, in a film drawn at its output frames.
2. liftmap.yml: the sectional lift of both cases against span and time, filling in
   from the left, drawn into DIR/frames/liftmap/.
3. The comparison again, with the film's output frames: three per wake frame, with a
   freeze of 24 frames at wake frame 15. The wakes are composed at their own rate,
   without the plots (DIR/frames/compare_flow/), and the plots drawn once per output
   frame (DIR/frames/plots_output/), for the film to lay over its interpolated frames.

tests/test_golden_compose.py checks frame 15 of the comparison and frame 20 of the lift
map against frames drawn by the prototype's own code.
"""
import shutil
import sys
from pathlib import Path

from flowreel import compose

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import case_data  # noqa: E402

FILES = ("flowreel.yml", "compare.yml", "plots.yml", "liftmap.yml")


def main(folder: Path) -> None:
    case_data.write_data(folder)
    for name in FILES:
        shutil.copy(HERE / name, folder / name)
    frames = folder / "frames"
    report = compose.layout(folder / "compare.yml", frames, panels={"jobs": 2})
    print(f"{report.folder.name}: {report.count('composed')} composed")
    report = compose.panel(folder / "liftmap.yml", frames, jobs=2)
    print(f"{report.folder.name}: {report.count('drawn')} drawn")
    output = compose.output_positions(len(case_data.WAKE_TIMES), per_frame=3, holds=[(15, 24)])
    report = compose.layout(folder / "compare.yml", frames, output=output, panels={"jobs": 2})
    print(f"{report.folder.name}: {report.count('composed')} composed, "
          f"{report.count('skipped')} skipped")
    for tile, panel in report.overlays:
        print(f"{panel.folder.name}: {panel.count('drawn')} drawn at {tile.at}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("compare_example"))
