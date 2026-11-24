"""Draw three frames of the staggered-groove shot side by side: carving, carved, close.

Usage: python run.py [OUT.png]   (default ./grooves.png)

Needs no data: the body is generated (the geometry source). Frames are drawn at a
quarter of the shot's size. docs/images/grooves.png is this script's output.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from flowreel.scene import render_frame

SHOT = Path(__file__).parent / "shots" / "grooves.yml"
FRAMES = (80, 160, 191)                     # front at mid-span; all carved; close in
SIZE = (480, 270)


def main(out: Path) -> None:
    tiles = [render_frame(SHOT, f, size=SIZE) for f in FRAMES]
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.hstack(tiles)).save(out, optimize=True)
    print(f"{out}: frames {', '.join(map(str, FRAMES))}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("grooves.png"))
