"""A riser 500 diameters long, generated, read through a window and drawn three ways.

Usage: python run.py [DIR] [--draft] [--image OUT.png]   (default ./riser500_example)

Needs no data: riser500_case.py writes the case into DIR (about 45 MB: eight steps of
a channel 500 long round the riser, the probes' and the pendulum's histories, and this
folder's flowreel.yml and shots). Then:

1. What one step costs, read whole and through travel.yml's window, and the same window
   in a case half as long: the same, because a window does not grow with the span.
2. travel.yml, span.yml and pendulum.yml are rendered into DIR/frames/. ``--draft``
   draws only their first and last frames, at half size.
3. With ``--image``, one frame of each shot side by side (docs/images/riser500.png is
   this script's output).
"""
import sys
from pathlib import Path

import numpy as np

from flowreel.scene import render, render_frame
from flowreel.scene.rendering import Scene
from flowreel.sources.flexflow import FlexflowSource

sys.path.insert(0, str(Path(__file__).parent))
import riser500_case as case  # noqa: E402

SHOTS = ("travel", "span", "pendulum")
STILLS = {"travel": 3, "span": 2, "pendulum": 1}


def main(folder: Path, draft: bool = False, image: Path | None = None) -> None:
    case.write_case(folder)
    travel = Scene.make(folder / "travel.yml")
    whole_mb = travel.source.memory_per_step(None) * 1e3
    window_mb = travel.source.memory_per_step(travel.crop(0)) * 1e3
    print(f"one step read whole: {whole_mb:.1f} MB; through the window: {window_mb:.2f} MB "
          f"({whole_mb / window_mb:.0f} times less)")
    half = case.write_case(folder / "half_span", length=250.0, project=False)
    short = FlexflowSource(half / "case", cache=None, margin=1.0)
    print(f"the same window in a case 250 long: "
          f"{short.memory_per_step(travel.crop(0)) * 1e3:.2f} MB")
    for i in (0, case.STEPS - 1):
        box = travel.crop(i)
        print(f"travel frame {i}: window x {box.lo[0]:.1f} to {box.hi[0]:.1f}, "
              f"{travel.data(i).flow.n_cells} of {1000 * 64} cells read")
    for shot in SHOTS:
        frames = [0, case.STEPS - 1] if draft else None
        report = render(folder / f"{shot}.yml", frames, out=folder / "frames", jobs=2,
                        scale=0.5 if draft else None)
        print(f"{shot}: {report.count('rendered')} drawn (backend {report.backend})")
    if image is not None:
        from PIL import Image
        tiles = [render_frame(folder / f"{s}.yml", STILLS[s]) for s in SHOTS]
        image.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.hstack(tiles)).save(image, optimize=True)
        print(f"{image}: one frame of each shot")


if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--image" in args:
        k = args.index("--image")
        out = Path(args[k + 1])
        del args[k:k + 2]
    draft = "--draft" in args
    rest = [a for a in args if a != "--draft"]
    main(Path(rest[0]) if rest else Path("riser500_example"), draft, out)
