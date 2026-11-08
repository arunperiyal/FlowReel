"""Render the frozen-time shots, where time stands still and the camera moves.

Usage: python render_frozen.py domain CASE_DIR OUT_DIR --time-step 5000 [--frames 288] [--jobs 8]

domain:  The whole computational domain as an outline, with the cylinder inside, the
         inflow marked, the clamped ends and the direction the cylinder may move. The
         view holds while the set-up is labelled (captions in film_text.toml), then moves
         in to the main view, the first view of the flow shot; the outline fades and the
         wake grows downstream from the cylinder.

The carving shot, also frozen, is made from geometry alone: render_carve.py.

Frames already in OUT_DIR are skipped, so an interrupted run can be restarted. Surfaces
are cached in OUT_DIR/cache, named by their level, so a new level makes a new cache.
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

# Importing render_frames also sets the rendering and thread options.
from render_frames import (CAMERA, COLOUR_FIELD, COLOUR_RANGE, FIRE_ICE, SIZE, VIEW_ANGLE,
                           WAKE_FIELD, WAKE_LEVEL, add_cylinder, load_step, new_plot, ramp)
from fxplt import PltFile
import pyvista as pv

# Domain shot, as fractions of the shot.
DOMAIN_HOLD = 0.6  # the wide view stays still this long, for the set-up labels
OUTLINE_FADE = (0.66, 0.9)
WAKE_GROWTH = (0.64, 0.97)  # the wake appears from the cylinder downstream
OUTLINE_COLOUR = "#8fa3b3"
INFLOW_COLOUR = "#6fb6d6"
CLAMP_COLOUR = "#8a9299"
MOTION_COLOUR = "#f5a142"
MOTION_LENGTH = 7.0  # of the double arrow showing cross-flow motion, in D


def between(a, b, t):
    return tuple((1 - t) * np.array(a) + t * np.array(b))


def domain_bounds(case, step):
    """Limits of the computational domain, from the points of the flow zone."""
    plt = PltFile(str(Path(case) / "binary" / f"riser.{step}.plt"))
    points = plt.load_zone(plt.first_volume_zone())[0]
    plt.close()
    return [float(v) for pair in zip(points.min(0), points.max(0)) for v in pair]


def domain_camera(bounds):
    """The main view's direction, moved back until the whole domain is in frame."""
    centre = np.array([(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2,
                       (bounds[4] + bounds[5]) / 2])
    eye, focal = np.array(CAMERA[0]), np.array(CAMERA[1])
    direction = (eye - focal) / np.linalg.norm(eye - focal)
    diagonal = np.linalg.norm(np.array(bounds[1::2]) - np.array(bounds[::2]))
    distance = 0.55 * diagonal / np.tan(np.radians(VIEW_ANGLE / 2))
    return [tuple(centre + distance * direction), tuple(centre), CAMERA[2]]


def inflow_arrows(bounds):
    """A grid of arrows on the inlet face, pointing downstream."""
    xs = np.linspace(bounds[0] + 2, bounds[1] - 2, 3)
    ys = np.linspace(bounds[2] + 5, bounds[3] - 5, 4)
    starts = np.array([(x, y, bounds[4] - 0.5) for x in xs for y in ys])
    arrows = pv.PolyData(starts)
    arrows["direction"] = np.tile([0.0, 0.0, 1.0], (len(starts), 1))
    return arrows.glyph(orient="direction", scale=False, factor=4.0,
                        geom=pv.Arrow(tip_length=0.3, tip_radius=0.12, shaft_radius=0.04))


def clamps(bounds):
    """A block at each end of the span, where the cylinder is clamped."""
    return [pv.Box((x - 0.4, x + 0.4, -1.0, 1.0, -1.0, 1.0)) for x in (bounds[0], bounds[1])]


def motion_arrow(bounds):
    """A double arrow along y at mid-span: the cylinder moves cross-flow only."""
    x, half = (bounds[0] + bounds[1]) / 2, MOTION_LENGTH / 2
    style = dict(tip_length=0.18, tip_radius=0.08, shaft_radius=0.03, scale=half)
    return [pv.Arrow(start=(x, 0.6, 0), direction=(0, 1, 0), **style),
            pv.Arrow(start=(x, -0.6, 0), direction=(0, -1, 0), **style)]


def domain_frame(job):
    cache, out, index, total = job
    target = Path(out) / f"frame_{index:05d}.png"
    if target.exists():
        return
    t = index / (total - 1)
    bounds = json.loads(Path(f"{cache}/bounds.json").read_text())
    eased = ramp(t, DOMAIN_HOLD, 1)
    start = domain_camera(bounds)
    camera = [between(start[i], CAMERA[i], eased) for i in range(3)]
    plot = new_plot(SIZE, camera, VIEW_ANGLE)
    add_cylinder(plot, pv.read(f"{cache}/cyl.vtp"))
    outline = 1 - float(ramp(t, *OUTLINE_FADE))
    if outline > 0:
        plot.add_mesh(pv.Box(bounds).outline(), color=OUTLINE_COLOUR, line_width=2.5,
                      opacity=outline, lighting=False)
        plot.add_mesh(inflow_arrows(bounds), color=INFLOW_COLOUR, opacity=outline, ambient=0.5)
        for block in clamps(bounds):
            plot.add_mesh(block, color=CLAMP_COLOUR, opacity=outline, ambient=0.4)
        for arrow in motion_arrow(bounds):
            plot.add_mesh(arrow, color=MOTION_COLOUR, opacity=outline, ambient=0.5)
    grown = float(ramp(t, *WAKE_GROWTH))
    if grown > 0:
        wake = pv.read(f"{cache}/wake_{WAKE_FIELD}_{WAKE_LEVEL:g}.vtp")
        front = wake.bounds[4] + (wake.bounds[5] - wake.bounds[4]) * grown
        wake = wake.clip("z", origin=(0, 0, front), invert=True) if grown < 1 else wake
        if wake.n_points:
            plot.add_mesh(wake, scalars=COLOUR_FIELD, cmap=FIRE_ICE, clim=COLOUR_RANGE,
                          smooth_shading=True, specular=0.3, ambient=0.25,
                          show_scalar_bar=False)
    plot.screenshot(str(target))
    plot.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shot", choices=["domain"])
    parser.add_argument("case")
    parser.add_argument("out")
    parser.add_argument("--time-step", type=int, default=5000)
    parser.add_argument("--frames", type=int)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    out = Path(args.out)
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    if args.shot == "domain":
        worker, frames = domain_frame, args.frames or 288
        wake = cache / f"wake_{WAKE_FIELD}_{WAKE_LEVEL:g}.vtp"
        if not wake.exists():
            _, cyl, iso = load_step(args.case, args.time_step)
            cyl.save(cache / "cyl.vtp")
            iso.extract_surface(algorithm="dataset_surface").save(wake)
        if not (cache / "bounds.json").exists():
            (cache / "bounds.json").write_text(json.dumps(domain_bounds(args.case, args.time_step)))
    jobs = [(str(cache), str(out), i, frames) for i in range(frames)]
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(worker, jobs))
    print(f"{out}: {frames} frames")


if __name__ == "__main__":
    main()
