"""Draw the golden frame of the carving shot with the prototype's ``render_carve.py``.

Usage: python tools/make_carve_golden.py [--out tests/data/carve]

The carving shot is made from geometry alone, so it needs no data: the prototype's own
``render_carve.frame`` draws frame ``FRAME`` of ``FRAMES`` into ``golden.png``. Only the
frame size is changed, to ``SIZE``; grooves, cutters, colours and camera keys are the
prototype's.

Not part of the package. Run it again only to change the golden frame on purpose.
"""
import argparse
import os
import sys

# Golden frames are drawn in software by OSMesa, whatever the machine has: it gives the
# same pixels wherever the same Mesa is installed, and GPU drivers draw wide lines
# differently (the domain outline differed by half its brightness under X). The
# prototype itself chose OSMesa on the workstation.
os.environ["VTK_DEFAULT_OPENGL_WINDOW"] = "vtkOSOpenGLRenderWindow"
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZE = (640, 360)
FRAMES, FRAME = 288, 115       # t = 0.40: the cutters halfway along the span, camera moving


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "carve")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import render_carve as rc

    rc.SIZE = SIZE
    frames = args.out / "golden_frames"
    frames.mkdir(parents=True, exist_ok=True)
    rc.frame((str(frames), FRAME, FRAMES))
    (frames / f"frame_{FRAME:05d}.png").replace(args.out / "golden.png")
    frames.rmdir()
    print(f"{args.out / 'golden.png'}: frame {FRAME} of {FRAMES}")


if __name__ == "__main__":
    main()
