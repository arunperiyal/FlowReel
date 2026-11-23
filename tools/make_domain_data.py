"""Make the small data set and the golden frame of the domain shot.

Usage: python tools/make_domain_data.py CASE_DIR [--step 5000] [--out tests/data/domain]

1. Data. Velocity of one step of a FlexFlow case is sampled on a coarse regular grid
   over the whole span and the near wake (``flow_<step>.vti``), the body is saved whole
   (``body.vtp``), and the domain's bounds go to ``domain.json``. The grid is coarse
   along the span (0.5 D), where the shed vortices barely change, and finer across
   (0.1 D): the data is for testing the picture, not the physics.
2. Golden frame. The prototype's own ``render_frozen.domain_frame`` draws frame
   ``FRAME`` of ``FRAMES`` from a cache built here the way ``render_frozen.main`` builds
   it (``load_step``'s wake: lambda2, wall gap, from the same data). Only the frame size
   is changed, to ``SIZE``; camera, timing, colours and markers are the prototype's.

Not part of the package. Run it again only to change the test data on purpose.
"""
import argparse
import os
import json
import sys

# Golden frames are drawn in software by OSMesa, whatever the machine has: it gives the
# same pixels wherever the same Mesa is installed, and GPU drivers draw wide lines
# differently (the domain outline differed by half its brightness under X). The
# prototype itself chose OSMesa on the workstation.
os.environ["VTK_DEFAULT_OPENGL_WINDOW"] = "vtkOSOpenGLRenderWindow"
from pathlib import Path

import numpy as np
import pyvista as pv

from flowreel.box import Box
from flowreel.sources.plt import PltSource

ROOT = Path(__file__).resolve().parent.parent
BOX = Box((0.0, -1.5, -1.0), (12.0, 2.5, 6.0))
SPACING = (0.5, 0.1, 0.1)
SIZE = (640, 360)
FRAMES, FRAME = 288, 224       # t = 0.78: outline half faded, wake 40% grown, camera moving in


def make_data(case: Path, step: int, out: Path) -> None:
    """Write ``flow_<step>.vti``, ``body.vtp`` and ``domain.json`` into ``out``."""
    src = PltSource(case)
    flow = src.flow(step, ["U", "V", "W"], BOX.expanded(0.5))
    dims = [int(round(s / d)) + 1 for s, d in zip(BOX.size, SPACING)]
    image = pv.ImageData(dimensions=dims, spacing=SPACING, origin=BOX.lo).sample(flow)
    small = pv.ImageData(dimensions=dims, spacing=SPACING, origin=BOX.lo)
    for name in ("U", "V", "W"):
        small.point_data[name] = np.asarray(image.point_data[name], dtype=np.float32)
    small.save(out / f"flow_{step}.vti")
    body = src.body(step)
    wall = pv.PolyData(body.points.astype(np.float32), body.faces)
    wall.save(out / "body.vtp")
    box = src.bounds()
    bounds = [float(v) for pair in zip(box.lo, box.hi) for v in pair]
    bounds = [round(v, 6) + 0.0 for v in bounds]          # -9e-16 is 0
    (out / "domain.json").write_text(json.dumps(bounds) + "\n")
    print(f"{out}: flow {dims} = {small.n_points} points, body {wall.n_cells} cells, "
          f"domain {bounds}")


def make_golden(out: Path, step: int) -> None:
    """Draw ``golden.png`` with ``render_frozen.domain_frame`` from the files in ``out``."""
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import render_frames as rf
    import render_frozen as rz

    rz.SIZE = SIZE
    cache = out / "golden_cache"
    cache.mkdir(exist_ok=True)
    mesh = rf.true_fields(pv.read(out / f"flow_{step}.vti").cast_to_unstructured_grid())
    cyl = pv.read(out / "body.vtp")
    iso = mesh.contour([rf.WAKE_LEVEL], scalars=rf.WAKE_FIELD)
    iso["gap"] = rf.cKDTree(cyl.points).query(iso.points)[0]
    iso = iso.clip_scalar(scalars="gap", value=rf.WALL_GAP, invert=False)
    cyl.save(cache / "cyl.vtp")
    iso.extract_surface(algorithm="dataset_surface").save(
        cache / f"wake_{rf.WAKE_FIELD}_{rf.WAKE_LEVEL:g}.vtp")
    (cache / "bounds.json").write_text((out / "domain.json").read_text())
    frames = out / "golden_frames"
    frames.mkdir(exist_ok=True)
    rz.domain_frame((str(cache), str(frames), FRAME, FRAMES))
    (frames / f"frame_{FRAME:05d}.png").replace(out / "golden.png")
    for d in (frames, cache):
        for f in d.iterdir():
            f.unlink()
        d.rmdir()
    print(f"{out / 'golden.png'}: frame {FRAME} of {FRAMES}, wide view {rz.domain_camera(json.loads((out / 'domain.json').read_text()))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--step", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "domain")
    parser.add_argument("--golden-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.golden_only:
        make_data(args.case, args.step, args.out)
    make_golden(args.out, args.step)


if __name__ == "__main__":
    main()
