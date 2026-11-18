"""Draw two frames of the axes shot side by side: from the front, and from above.

Usage: python run.py [OUT.png]   (default ./axes.png)

Needs no data: the body is generated (the geometry source). Frames are drawn at half
the shot's size; the labels and the triad shrink with them, as in any draft.
docs/images/axes.png is this script's output.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from flowreel.scene import render_frame

SHOT = Path(__file__).with_name("shot.yml")
FRAMES = (0, 48)                  # from above, y points at the camera: not ruled
SIZE = (960, 540)


def main(out: Path) -> None:
    tiles = [render_frame(SHOT, f, size=SIZE) for f in FRAMES]
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.hstack(tiles)).save(out, optimize=True)
    print(f"{out}: frames {', '.join(map(str, FRAMES))}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("axes.png"))
