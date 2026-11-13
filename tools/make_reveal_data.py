"""Make the small data set and the golden frame of the reveal test.

Usage: python tools/make_reveal_data.py CASE_DIR [--step 5000] [--out tests/data/reveal]

1. Data. Velocity of one step of a FlexFlow case is sampled on a coarse regular grid in
   a box around mid-span (``flow_<step>.vti``), and the part of the body inside the box
   is saved next to it (``body.vtp``). The grid does not follow the wall and is far
   coarser than the mesh: the data is for testing the picture, not the physics.
2. Golden frame. The prototype's own functions (``prototype/afms/render_frames.py``:
   ``true_fields``, ``add_reveal``, ``add_cylinder``, ``new_plot``) draw the reveal look
   from that data at the sweep progress, camera and size in ``tests/data/reveal/shot.yml``.
   The prototype's sweep ends (``SWEEP_START``, ``MIDSPAN``) and wake crop are set to the
   shot's, since the box is shorter than the span; nothing else of the prototype changes.

Not part of the package. Run it again only to change the test data on purpose.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pyvista as pv
import yaml

from flowreel.box import Box
from flowreel.sources.flexflow import FlexflowSource

ROOT = Path(__file__).resolve().parent.parent
BOX = Box((4.0, -1.5, -1.0), (8.0, 2.5, 5.0))
SPACING = (0.2, 0.1, 0.1)


def make_data(case: Path, step: int, out: Path) -> None:
    """Write ``flow_<step>.vti`` and ``body.vtp`` into ``out``."""
    src = FlexflowSource(case)
    flow = src.flow(step, ["U", "V", "W"], BOX.expanded(0.5))
    dims = [int(round(s / d)) + 1 for s, d in zip(BOX.size, SPACING)]
    image = pv.ImageData(dimensions=dims, spacing=SPACING, origin=BOX.lo).sample(flow)
    small = pv.ImageData(dimensions=dims, spacing=SPACING, origin=BOX.lo)
    for name in ("U", "V", "W"):
        small.point_data[name] = np.asarray(image.point_data[name], dtype=np.float32)
    small.save(out / f"flow_{step}.vti")
    body = src.body(step)
    inside = BOX.contains(body.cell_centers().points)
    body = body.extract_cells(np.flatnonzero(inside)).extract_surface(algorithm="dataset_surface")
    wall = pv.PolyData(body.points.astype(np.float32), body.faces)
    wall.save(out / "body.vtp")
    print(f"{out}: flow {dims} = {small.n_points} points, body {wall.n_cells} cells")


def make_golden(out: Path, step: int) -> None:
    """Draw ``golden.png`` with the prototype's functions from the files in ``out``."""
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import render_frames as rf

    shot = yaml.safe_load((out / "shot.yml").read_text())
    rf.SWEEP_START, rf.MIDSPAN = shot["sweep"]["from"], shot["sweep"]["to"]
    first, last = shot["sweep"]["frames"]
    progress = float(np.clip((shot["frame"] - first) / (last - first), 0, 1))

    mesh = pv.read(out / f"flow_{step}.vti").cast_to_unstructured_grid()
    mesh = rf.true_fields(mesh)
    cyl = pv.read(out / "body.vtp")
    iso = mesh.contour([rf.WAKE_LEVEL], scalars=rf.WAKE_FIELD)
    iso["gap"] = rf.cKDTree(cyl.points).query(iso.points)[0]
    iso = iso.clip_scalar(scalars="gap", value=rf.WALL_GAP, invert=False)

    plot = rf.new_plot(shot["size"], [tuple(v) for v in shot["camera"]], shot["view_angle"])
    rf.add_cylinder(plot, cyl)
    rf.add_look(plot, "reveal", mesh, iso, cyl, progress)
    plot.screenshot(str(out / "golden.png"))
    plot.close()
    print(f"{out / 'golden.png'}: progress {progress}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--step", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "reveal")
    parser.add_argument("--golden-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.golden_only:
        make_data(args.case, args.step, args.out)
    make_golden(args.out, args.step)


if __name__ == "__main__":
    main()
