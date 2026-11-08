"""The shots that explain the suppression: wall shear, sectional lift and a groove section.

Usage: python render_extras.py wall SURFACE_DIR OUT_DIR [--t1 5000] [--t2 5240] [--jobs 8]
       python render_extras.py liftmap BARE_SURFACE_DIR HELICAL_SURFACE_DIR OUT_DIR [--frames 144]
       python render_extras.py section CASE_DIR OUT_DIR [--t1 5000] [--t2 5240] [--jobs 8]
       python render_extras.py spanslices CASE_DIR OUT_DIR [--t1 5000] [--t2 5240] [--jobs 8]

wall:    The body seen from above (y), span across the frame, coloured by the streamwise
         skin friction: warm where the flow runs downstream over the wall, cold where it
         runs back. The white line between them is where the flow leaves the wall. One
         1920 x 540 strip per step; compose_compare.py stacks two cases.
liftmap: Sectional lift of both cases against span and time, filling in from left to
         right, one frame per 24 fps frame.
section: Mid-span section of one case: spanwise vorticity, the flow relative to the
         moving body, and a close view of a groove edge. One frame per step.
spanslices: Spanwise vorticity in flat cuts at several places along the span, side by
         side, so the phase of shedding can be read across the row. One 1920 x 540 strip
         per step; compose_compare.py stacks two cases.

SURFACE_DIR is made by surface_data.py. Frames already in OUT_DIR are skipped. Labels
and case names come from film_text.toml.
"""
import argparse
import io
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import render_frames as rf
import pyvista as pv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
from PIL import Image
from matplotlib.path import Path as Outline
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

from fxplt import PltFile

ROOT = Path(__file__).resolve().parent
DT = 0.05
STRIP = (1920, 540)
# The body from above and behind, square on to the top rear quarter where the flow
# leaves the wall, with the span across the strip.
WALL_CAMERA = [(6, 6, 6), (6, 0.25, 0.25), (0, 1, -1)]
WALL_SCALE = 1.75  # half the strip height, in D
CF_RANGE = (-0.03, 0.03)  # streamwise skin friction
SPAN_SLICES = (3.0, 6.0, 9.0)  # quarter, half and three-quarter span
SLICE_WINDOW = ((-1.5, 8.5), (-4.2, 4.2))  # z then y, in D: the near wake
SLICE_RANGE = (-2.5, 2.5)  # spanwise vorticity, as on the 3D slices
LIFT_RANGE = (-1.5, 1.5)
SECTION_HALF = 1.4  # half-width of the section view, in D
ZOOM_HALF = 0.3
VOR_RANGE = (-30, 30)  # spanwise vorticity near the wall is far stronger than in the wake
GRID, AXIS, WHITE = "#3a4046", "#b4bec8", "#f2f2f2"


def load_text():
    with open(ROOT / "film_text.toml", "rb") as f:
        return tomllib.load(f)


def style():
    plt.rcParams.update({"font.family": ["Lato", "DejaVu Sans"], "font.size": 20,
                         "mathtext.fontset": "dejavusans", "axes.edgecolor": GRID,
                         "axes.labelcolor": AXIS, "xtick.color": AXIS, "ytick.color": AXIS})


def save(fig, path):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor="black")
    Image.open(buffer).convert("RGB").save(path)


# --- wall --------------------------------------------------------------------------

def wall_frame(job):
    data_file, target = job
    if Path(target).exists():
        return
    d = np.load(data_file)
    cells = np.c_[np.full(len(d["cells"]), 3), d["cells"]].ravel()
    body = pv.PolyData(d["points"], cells)
    body.cell_data["cf_z"] = d["cf"][:, 2]
    smooth = body.cell_data_to_point_data()
    line = smooth.contour([0.0], scalars="cf_z")
    plot = pv.Plotter(off_screen=True, window_size=STRIP)
    plot.set_background("black")
    plot.camera_position = WALL_CAMERA
    plot.enable_parallel_projection()
    plot.camera.parallel_scale = WALL_SCALE
    plot.enable_anti_aliasing("ssaa")
    plot.add_mesh(smooth, scalars="cf_z", cmap=rf.FIRE_ICE, clim=CF_RANGE, smooth_shading=True,
                  specular=0.2, ambient=0.35, show_scalar_bar=False)
    if line.n_points:
        plot.add_mesh(line, color=WHITE, line_width=4, lighting=False)
    plot.screenshot(str(target))
    plot.close()


def wall(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    steps = range(args.t1, args.t2 + 1, args.step)
    jobs = [(Path(args.data) / f"step_{s}.npz", out / f"frame_{i:05d}.png")
            for i, s in enumerate(steps)]
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(wall_frame, jobs))
    print(f"{out}: {len(jobs)} frames")


# --- liftmap -----------------------------------------------------------------------

def lift_table(folder):
    files = sorted(Path(folder).glob("step_*.npz"), key=lambda p: int(p.stem.split("_")[1]))
    steps = np.array([int(p.stem.split("_")[1]) for p in files])
    return steps * DT, np.array([np.load(p)["lift"] for p in files])


def liftmap(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    text = load_text()
    style()
    tables = {"bare": lift_table(args.data), "helical": lift_table(args.data2)}
    fig, axes = plt.subplots(2, 1, figsize=(19.2, 10.8), dpi=100, sharex=True)
    fig.patch.set_facecolor("black")
    # Plots on the left two-thirds; the right is kept clear for the caption.
    fig.subplots_adjust(left=0.07, right=0.66, top=0.93, bottom=0.1, hspace=0.25)
    images = []
    for ax, (case, (t, lift)) in zip(axes, tables.items()):
        ax.set_facecolor("black")
        span = (np.arange(lift.shape[1]) + 0.5) * 12 / lift.shape[1]  # strip centres
        image = ax.pcolormesh(t, span, np.full((lift.shape[1], len(t)), np.nan), cmap=rf.FIRE_ICE,
                              vmin=LIFT_RANGE[0], vmax=LIFT_RANGE[1], shading="nearest")
        images.append((image, t, lift))
        ax.set_ylabel(text["plots"]["span"])
        ax.set_title(text["cases"][case]["name"], loc="left", color=text["cases"][case]["colour"],
                     fontsize=26)
        ax.tick_params(length=0)
        ax.set_yticks([3, 6, 9])
        ax.set_xlim(t[0], t[-1])
    axes[-1].set_xlabel(text["plots"]["time"])
    bar = fig.colorbar(images[0][0], ax=axes, fraction=0.025, pad=0.02)
    bar.set_label(text["plots"]["sectional_lift"])
    bar.outline.set_edgecolor(GRID)
    t0, t1 = images[0][1][0], images[0][1][-1]
    for i in range(args.frames):
        target = out / f"frame_{i:05d}.png"
        now = t0 + (t1 - t0) * i / (args.frames - 1)
        for image, t, lift in images:
            shown = np.where(t[None, :] <= now + 1e-9, lift.T, np.nan)
            image.set_array(shown.ravel())
        save(fig, target)
    print(f"{out}: {args.frames} frames")


# --- section -----------------------------------------------------------------------

def section_data(case, step):
    """Mid-span cut: triangulation, vorticity, lambda2, velocity, and the body outline."""
    saved = rf.CROP
    rf.CROP = ((5.0, 7.0), (-3, 3), (-2.5, 3.5))
    plt_ = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    index = plt_.first_volume_zone()
    points, conn, data, _ = plt_.load_zone(index)
    ztype = plt_.zones[index]["ztype"]
    plt_.close()
    mesh = rf.true_fields(rf.grid(*rf.crop(points, conn, {k: data[k] for k in "UVW"}), ztype))
    rf.CROP = saved
    cut = mesh.slice(normal="x", origin=(rf.MIDSPAN, 0, 0)).triangulate()
    ring = rf.load_cylinder(case, step).slice(normal="x", origin=(rf.MIDSPAN, 0, 0))
    return cut, ring


def section_frame(job):
    case, target, step, zoom_offset = job
    if Path(target).exists():
        return
    cut, ring = section_data(case, step)
    y, z = cut.points[:, 1].astype(float), cut.points[:, 2].astype(float)
    yc, zc = float(ring.points[:, 1].mean()), float(ring.points[:, 2].mean())
    # The body moves in y only; the wall nodes move with it, so their velocity is its own.
    on_wall = cKDTree(ring.points).query(cut.points)[0] < 1e-3
    body_v = float(cut["vel"][on_wall, 1].mean())
    tri = Triangulation(z, y, cut.faces.reshape(-1, 4)[:, 1:])
    style()
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor("black")
    views = [(fig.add_axes([0.04, 0.08, 0.5, 0.84]), (zc, yc), SECTION_HALF, 1.6),
             (fig.add_axes([0.58, 0.2, 0.38, 0.6]), (zc + zoom_offset[0], yc + zoom_offset[1]),
              ZOOM_HALF, 2.4)]
    for ax, (cz, cy), half, density in views:
        ax.set_facecolor("black")
        ax.tricontourf(tri, cut["xVor_true"], levels=np.linspace(*VOR_RANGE, 41),
                       cmap=rf.FIRE_ICE, extend="both")
        Z, Y = np.meshgrid(np.linspace(cz - half, cz + half, 260), np.linspace(cy - half, cy + half, 260))
        w = griddata((z, y), cut["vel"][:, 2], (Z, Y))
        v = griddata((z, y), cut["vel"][:, 1] - body_v, (Z, Y))
        inside = inside_body(ring, Z, Y)
        w[inside], v[inside] = np.nan, np.nan
        ax.streamplot(Z, Y, w, v, color=(1, 1, 1, 0.55), density=density, linewidth=0.7,
                      arrowsize=0.8)
        ax.fill(*outline(ring), color="#c8ccd0", zorder=3)
        ax.set_xlim(cz - half, cz + half)
        ax.set_ylim(cy - half, cy + half)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    # Mark the zoomed window on the full view.
    big, small = views[0][0], views[1]
    (cz, cy), half = small[1], small[2]
    big.add_patch(matplotlib.patches.Rectangle((cz - half, cy - half), 2 * half, 2 * half,
                                               fill=False, edgecolor=WHITE, linewidth=1.5, zorder=4))
    save(fig, target)
    plt.close(fig)


def spanslice_frame(job):
    case, target, step = job
    if Path(target).exists():
        return
    saved = rf.CROP
    (z0, z1), (y0, y1) = SLICE_WINDOW
    rf.CROP = ((0, 12), (y0 - 0.5, y1 + 0.5), (z0 - 0.5, z1 + 0.5))
    plt_ = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    index = plt_.first_volume_zone()
    points, conn, data, _ = plt_.load_zone(index)
    ztype = plt_.zones[index]["ztype"]
    plt_.close()
    mesh = rf.true_fields(rf.grid(*rf.crop(points, conn, {k: data[k] for k in "UVW"}), ztype))
    rf.CROP = saved
    cyl = rf.load_cylinder(case, step)
    style()
    fig = plt.figure(figsize=(STRIP[0] / 100, STRIP[1] / 100), dpi=100)
    fig.patch.set_facecolor("black")
    width = 1 / len(SPAN_SLICES)
    for k, x in enumerate(SPAN_SLICES):
        ax = fig.add_axes([k * width + 0.004, 0.09, width - 0.008, 0.91])
        ax.set_facecolor("black")
        cut = mesh.slice(normal="x", origin=(x, 0, 0)).triangulate()
        tri = Triangulation(cut.points[:, 2], cut.points[:, 1], cut.faces.reshape(-1, 4)[:, 1:])
        ax.tricontourf(tri, cut["xVor_true"], levels=np.linspace(*SLICE_RANGE, 41),
                       cmap=rf.FIRE_ICE, extend="both")
        ring = cyl.slice(normal="x", origin=(x, 0, 0))
        ax.fill(*outline(ring), color="#c8ccd0", zorder=3)
        ax.set_xlim(z0, z1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(0.5, -0.02, f"x = {x:g} D", transform=ax.transAxes, ha="center", va="top",
                color=AXIS, fontsize=20)
    save(fig, target)
    plt.close(fig)


def spanslices(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    case = Path(args.case).resolve()
    steps = range(args.t1, args.t2 + 1, args.step)
    jobs = [(case, out / f"frame_{i:05d}.png", s) for i, s in enumerate(steps)]
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(spanslice_frame, jobs))
    print(f"{out}: {len(jobs)} frames")


def outline(ring):
    """The body outline at mid-span as a closed polygon, ordered by angle."""
    zc, yc = ring.points[:, 2].mean(), ring.points[:, 1].mean()
    order = np.argsort(np.arctan2(ring.points[:, 1] - yc, ring.points[:, 2] - zc))
    return ring.points[order, 2], ring.points[order, 1]


def inside_body(ring, Z, Y):
    zs, ys = outline(ring)
    return Outline(np.c_[zs, ys]).contains_points(np.c_[Z.ravel(), Y.ravel()]).reshape(Z.shape)


def section(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    case = Path(args.case).resolve()
    # The close view sits on the groove edge with the strongest lambda2 near the top of
    # the body in the first step, kept at the same place relative to the body.
    cut, ring = section_data(case, args.t1)
    y, z = cut.points[:, 1], cut.points[:, 2]
    yc, zc = ring.points[:, 1].mean(), ring.points[:, 2].mean()
    k = int(np.argmax(np.where(cut["lambda2"] < -50, y, -9)))
    offset = (float(z[k] - zc), float(y[k] - yc))
    steps = range(args.t1, args.t2 + 1, args.step)
    jobs = [(case, out / f"frame_{i:05d}.png", s, offset) for i, s in enumerate(steps)]
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(section_frame, jobs))
    print(f"{out}: {len(jobs)} frames")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shot", choices=["wall", "liftmap", "section", "spanslices"])
    parser.add_argument("data", help="SURFACE_DIR, or CASE_DIR for section")
    parser.add_argument("data2", nargs="?", help="helical SURFACE_DIR, for liftmap")
    parser.add_argument("out", nargs="?")
    parser.add_argument("--t1", type=int, default=5000)
    parser.add_argument("--t2", type=int, default=5240)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--frames", type=int, default=144)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.shot != "liftmap":  # two positional paths only
        args.out = args.data2
    args.case = args.data
    {"wall": wall, "liftmap": liftmap, "section": section,
     "spanslices": spanslices}[args.shot](args)


if __name__ == "__main__":
    main()
