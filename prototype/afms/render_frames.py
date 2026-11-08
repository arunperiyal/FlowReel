"""Render one video frame per PLT, on black, with a fixed camera and fixed scales.

Usage: python render_frames.py CASE_DIR OUT_DIR --t1 5000 --t2 5400 [--step 5] [--jobs 4]
                               [--look wake|grey|reveal] [--reveal-start F --reveal-end F]
                               [--view main|panel|top]

The panel view is a wide strip for compose_compare.py, which stacks two cases. The top
view looks straight down on the wake, span across and flow down the frame, without
perspective; compose_compare.py --across sets two of them side by side.

The reveal look starts as the full coloured wake. Between frames F, a cutting plane
sweeps along the span to mid-span, showing a live section, and the wake turns grey.

Each PLT is read directly with fxplt.py, a copy of the flexflow reader, so flexflow
itself is not needed. Frames already in OUT_DIR are skipped, so an interrupted run can
be restarted. With no display, frames are drawn in software by OSMesa.
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Set before VTK loads. With no display, draw in software: OSMesa where installed (the
# workstation), otherwise Mesa EGL (airavata). Each job stays on a few threads, so that
# --jobs sets the load.
if not os.environ.get("DISPLAY"):
    from ctypes.util import find_library
    window = "vtkOSOpenGLRenderWindow" if find_library("OSMesa") else "vtkEGLRenderWindow"
    os.environ.setdefault("VTK_DEFAULT_OPENGL_WINDOW", window)
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VTK_SMP_MAX_THREADS", "LP_NUM_THREADS"):
    os.environ.setdefault(name, "4")

import numpy as np
import pyvista as pv
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from scipy.spatial import cKDTree

from fxplt import PltFile

SIZE = (1920, 1080)
# The wake surface: a field recomputed from velocity (see true_fields) and its level.
# Lambda2 is negative inside vortices. Q at 0.1 gave a noisy wake; lambda2 at -0.5
# gave clean, separate tubes; -1 is your choice, sparser still.
WAKE_FIELD, WAKE_LEVEL = "lambda2", -1.0
WALL_GAP = 0.4  # hides the high-Q sheath wrapped around the body
CROP = ((-1, 13), (-6, 6), (-2, 25))  # x, y and z limits of the rendered wake
# Tubes and slice are coloured by the same quantity on the same scale, so that where the
# cutting plane crosses a tube their colours agree: spanwise vorticity, the rotation of
# the shed vortices about the cylinder axis.
COLOUR_FIELD, COLOUR_RANGE = "xVor_true", (-2.5, 2.5)
MIDSPAN = 6.0
SWEEP_START = 0.02  # the cutting plane starts at the end of the span nearest the camera
MUTED = "#6f8796"
# Looks across the span and downstream, flow left to right.
CAMERA = [(-19, 13, -5), (6, 0, 8.5), (0, 1, 0)]
VIEW_ANGLE = 30
VIEWS = {
    "main": dict(size=SIZE, camera=CAMERA, angle=VIEW_ANGLE),
    # A flatter view: two wakes stack on the left of one 1920 x 1080 frame, beside plots.
    "panel": dict(size=(1280, 540), camera=[(-30, 8, 1), (6, 0, 9.5), (0, 1, 0)], angle=17.5),
    # Straight down on the wake: span across, flow down the frame, half-height in D.
    "top": dict(size=(960, 1080), camera=[(6, 40, 9.5), (6, 0, 9.5), (0, 0, -1)], angle=30,
                parallel=10.6),
}
# Black at zero, so weak flow fades into the background.
FIRE_ICE = LinearSegmentedColormap.from_list(
    "fire_ice", ["#c8f6ff", "#00b4e6", "#043a66", "#000000", "#6a1500", "#f25c05", "#ffe08a"])


def true_fields(mesh):
    """Add Q, lambda2 and vorticity computed from velocity.

    The stored QCriterion and vorticity are not comparable between cases: against
    values recomputed from velocity, stored Q is 13.5 times larger on the brick mesh
    and 50 times larger on the tet mesh. Velocity is the same quantity in both.
    """
    mesh["vel"] = np.c_[mesh["U"], mesh["V"], mesh["W"]]
    grad = mesh.compute_derivative(scalars="vel", gradient="grad")["grad"].reshape(-1, 3, 3)
    strain = 0.5 * (grad + grad.transpose(0, 2, 1))
    spin = 0.5 * (grad - grad.transpose(0, 2, 1))
    mesh["Q_true"] = 0.5 * ((spin ** 2).sum((1, 2)) - (strain ** 2).sum((1, 2)))
    # lambda2: the middle eigenvalue of S^2 + W^2 (Jeong and Hussain 1995).
    mesh["lambda2"] = np.linalg.eigvalsh(strain @ strain + spin @ spin)[:, 1]
    mesh["zVor_true"] = grad[:, 1, 0] - grad[:, 0, 1]
    mesh["xVor_true"] = grad[:, 2, 1] - grad[:, 1, 2]
    return mesh


def grid(points, conn, data, ztype):
    """An unstructured grid from one PLT zone."""
    npe = conn.shape[1]
    if npe == 4:
        cell = pv.CellType.QUAD if ztype == 3 else pv.CellType.TETRA
    else:
        cell = {3: pv.CellType.TRIANGLE, 8: pv.CellType.HEXAHEDRON}[npe]
    mesh = pv.UnstructuredGrid({cell: conn}, points)
    for name, values in data.items():
        mesh[name] = values
    return mesh


def crop(points, conn, data):
    """Keep cells with every node inside CROP."""
    inside = np.ones(len(points), dtype=bool)
    for axis, (low, high) in enumerate(CROP):
        inside &= (points[:, axis] >= low) & (points[:, axis] <= high)
    conn = conn[inside[conn].all(axis=1)]
    used = np.unique(conn)
    renumber = np.full(len(points), -1, dtype=np.int64)
    renumber[used] = np.arange(len(used))
    return points[used], renumber[conn], {k: v[used] for k, v in data.items()}


def load_cylinder(case, step):
    """The body surface at one step."""
    plt = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    index = next(i for i, zone in enumerate(plt.zones) if zone["name"] == "cyl")
    points, conn, data, _ = plt.load_zone(index)
    surface = grid(points, conn, {}, plt.zones[index]["ztype"])
    plt.close()
    return surface.extract_surface(algorithm="dataset_surface")


def load_step(case, step):
    """The cropped flow with true fields, the body, and the wake surface at one step."""
    plt = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    index = plt.first_volume_zone()
    points, conn, data, _ = plt.load_zone(index)
    ztype = plt.zones[index]["ztype"]
    plt.close()
    data = {name: data[name] for name in ("U", "V", "W")}
    mesh = true_fields(grid(*crop(points, conn, data), ztype))
    cyl = load_cylinder(case, step)
    iso = mesh.contour([WAKE_LEVEL], scalars=WAKE_FIELD)
    iso["gap"] = cKDTree(cyl.points).query(iso.points)[0]
    return mesh, cyl, iso.clip_scalar(scalars="gap", value=WALL_GAP, invert=False)


def ramp(z, start, end):
    """0 before start, 1 after end, smooth between."""
    t = np.clip((z - start) / (end - start), 0, 1)
    return t * t * (3 - 2 * t)


def add_slice(plot, mesh, cyl, x=MIDSPAN, strength=1.0):
    """Cut of spanwise vorticity at x. Weak flow and the body surface fade out."""
    cut = mesh.slice(normal="x", origin=(x, 0, 0)).triangulate()
    cut = cut.compute_implicit_distance(cyl.triangulate())
    value = cut[COLOUR_FIELD]
    low, high = COLOUR_RANGE
    rgba = FIRE_ICE((value - low) / (high - low))
    rgba[:, 3] = (ramp(np.abs(value), 0.05, 0.5)
                  * ramp(np.abs(cut["implicit_distance"]), 0.03, 0.1) * strength)
    cut["rgba"] = (rgba * 255).astype(np.uint8)
    plot.add_mesh(cut, scalars="rgba", rgb=True, lighting=False, show_scalar_bar=False)


def add_reveal(plot, mesh, iso, cyl, progress):
    """The cutting plane has travelled the fraction progress of the way to mid-span."""
    x = SWEEP_START + (MIDSPAN - SWEEP_START) * ramp(progress, 0, 1)
    add_slice(plot, mesh, cyl, x, strength=ramp(progress, 0, 0.1))
    wake = iso.clip("x", origin=(x, 0, 0), invert=False) if progress > 0 else iso
    low, high = COLOUR_RANGE
    colour = FIRE_ICE((wake[COLOUR_FIELD] - low) / (high - low))[:, :3]
    grey = ramp(progress, 0.4, 1.0)
    colour = (1 - grey) * colour + grey * np.array(to_rgb(MUTED))
    wake["rgb"] = (colour * 255).astype(np.uint8)
    plot.add_mesh(wake, scalars="rgb", rgb=True, smooth_shading=True, specular=0.3,
                  ambient=0.25, show_scalar_bar=False)


def add_look(plot, look, mesh, iso, cyl, progress=0.0):
    if look == "reveal":
        add_reveal(plot, mesh, iso, cyl, progress)
    elif look == "grey":
        add_slice(plot, mesh, cyl)
        half = iso.clip("x", origin=(MIDSPAN, 0, 0), invert=False)
        plot.add_mesh(half, color=MUTED, smooth_shading=True, specular=0.4, specular_power=30,
                      ambient=0.2, show_scalar_bar=False)
    else:
        plot.add_mesh(iso, scalars=COLOUR_FIELD, cmap=FIRE_ICE, clim=COLOUR_RANGE,
                      smooth_shading=True, specular=0.3, ambient=0.25, show_scalar_bar=False)


def new_plot(size, camera, angle, parallel=None):
    plot = pv.Plotter(off_screen=True, window_size=size)
    plot.set_background("black")
    plot.camera_position = camera
    plot.camera.view_angle = angle
    if parallel:
        plot.enable_parallel_projection()
        plot.camera.parallel_scale = parallel
    plot.enable_anti_aliasing("ssaa")
    return plot


def add_cylinder(plot, cyl, opacity=1.0):
    plot.add_mesh(cyl, color="#c8ccd0", smooth_shading=True, split_sharp_edges=True,
                  specular=0.4, specular_power=20, ambient=0.25, opacity=opacity)


def render(job):
    case, out, step, frame, look, progress, view = job
    view = VIEWS[view]
    target = Path(out) / f"frame_{frame:05d}.png"
    if target.exists():
        return step, 0.0
    start = time.time()
    mesh, cyl, iso = load_step(case, step)
    plot = new_plot(view["size"], view["camera"], view["angle"], view.get("parallel"))
    add_cylinder(plot, cyl)
    add_look(plot, look, mesh, iso, cyl, progress)
    plot.screenshot(str(target))
    plot.close()
    return step, time.time() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("out")
    parser.add_argument("--t1", type=int, required=True)
    parser.add_argument("--t2", type=int, required=True)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--look", choices=["wake", "grey", "reveal"], default="wake")
    parser.add_argument("--view", choices=list(VIEWS), default="main")
    parser.add_argument("--reveal-start", type=int, default=0)
    parser.add_argument("--reveal-end", type=int, default=1)
    args = parser.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    case = Path(args.case).resolve()
    steps = range(args.t1, args.t2 + 1, args.step)
    span = max(args.reveal_end - args.reveal_start, 1)
    jobs = [(case, args.out, s, i, args.look,
             float(np.clip((i - args.reveal_start) / span, 0, 1)), args.view)
            for i, s in enumerate(steps)]
    with ProcessPoolExecutor(args.jobs) as pool:
        for step, seconds in pool.map(render, jobs):
            print(f"{step}: {seconds:.1f} s", flush=True)


if __name__ == "__main__":
    main()
