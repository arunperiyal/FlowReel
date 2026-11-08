"""The carving shot: helical grooves are cut into the smooth cylinder. Made from geometry,
with no flow data.

Usage: python render_carve.py OUT_DIR [--frames 288] [--jobs 8] [--anchors]

The grooves match the helical case (riser.geo, and the simulated surface): four grooves,
GROOVE_DEPTH deep and GROOVE_WIDTH wide, each making one full turn over the 12 D span,
centred at 45 degrees plus multiples of 90 degrees at x = 0 (measured as atan2(y, z)).

Four glowing cutters run along the span and the grooves open behind them, the camera
moving around the whole cylinder; it then closes in at mid-span to show the groove shape,
and ends on the main view of the flow shots, so the helical wake reveal can follow.

--anchors prints where chosen points fall on the screen at a few moments, for placing
captions and arrows in film_text.toml. Frames already in OUT_DIR are skipped.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

# Importing render_frames also sets the rendering and thread options.
from render_frames import CAMERA, SIZE, VIEW_ANGLE, new_plot, ramp
import pyvista as pv

SPAN, RADIUS = 12.0, 0.5
GROOVE_DEPTH, GROOVE_WIDTH = 0.08, 0.2
GROOVES = 4
HALF_ANGLE = np.arcsin(GROOVE_WIDTH)  # half the groove's angular width (riser.geo Theta_g)
EDGE = 0.012  # radians over which a groove wall turns, to keep it smooth to the eye
SAMPLES = (721, 1441)  # along the span, around the body

CARVE = (0.18, 0.6)  # fraction of the shot over which the cutters run along the span
FRESH = 0.8  # length behind a cutter, in D, over which a new groove glows
BODY_COLOUR = np.array([0.83, 0.85, 0.86])
GROOVE_COLOUR = np.array([0.96, 0.63, 0.26])  # the helical case's colour
CUTTER_COLOUR = "#ffd08a"

CENTRE = (6.0, 0.0, 0.0)
# Camera keys: (fraction of the shot, eye, focal point, view angle). The camera eases
# from one key to the next; the last is the main view of the flow shots.
KEYS = [
    (0.0, (-2.0, 7.2, -11.8), CENTRE, 30),
    (0.6, (2.8, 8.0, -13.4), CENTRE, 30),
    (0.76, (4.4, 1.7, -2.7), (6.0, 0.0, 0.0), 34),
    (0.84, (4.4, 1.7, -2.7), (6.0, 0.0, 0.0), 34),
    (0.98, CAMERA[0], CAMERA[1], VIEW_ANGLE),
]


def groove_angle(x, k):
    return np.pi / 4 + k * np.pi / 2 + 2 * np.pi * x / SPAN


def camera_at(t):
    for (t0, e0, f0, a0), (t1, e1, f1, a1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            s = float(ramp(t, t0, t1))
            return ([tuple((1 - s) * np.array(e0) + s * np.array(e1)),
                     tuple((1 - s) * np.array(f0) + s * np.array(f1)), (0, 1, 0)],
                    (1 - s) * a0 + s * a1)
    return [KEYS[-1][1], KEYS[-1][2], (0, 1, 0)], KEYS[-1][3]


def body(front):
    """The cylinder with grooves cut up to x = front, and a glow along fresh cuts."""
    x = np.linspace(0, SPAN, SAMPLES[0])[:, None]
    theta = np.linspace(-np.pi, np.pi, SAMPLES[1])[None, :]
    inside = np.zeros((SAMPLES[0], SAMPLES[1]))
    for k in range(GROOVES):
        off = np.abs((theta - groove_angle(x, k) + np.pi) % (2 * np.pi) - np.pi)
        inside = np.maximum(inside, 1 - ramp(off, HALF_ANGLE - EDGE, HALF_ANGLE + EDGE))
    cut = np.clip((front - x) / 0.25, 0, 1) * np.ones_like(theta)
    depth = inside * cut
    r = RADIUS - GROOVE_DEPTH * depth
    grid = pv.StructuredGrid(x * np.ones_like(theta), r * np.sin(theta), r * np.cos(theta))
    fresh = depth * np.clip(1 - (front - x) / FRESH, 0, 1)
    colour = (BODY_COLOUR + (GROOVE_COLOUR - BODY_COLOUR) * (0.45 * depth)[..., None]
              + 0.6 * fresh[..., None] * (np.array([1.0, 0.85, 0.55]) - BODY_COLOUR))
    colour = np.clip(colour, 0, 1) * 255
    # Grid points run along the first axis fastest, so each channel is flattened that way.
    grid["rgb"] = np.stack([colour[..., c].ravel(order="F") for c in range(3)], 1).astype(np.uint8)
    surface = grid.extract_surface(algorithm="dataset_surface")
    caps = []
    for end in (0, -1):
        ring = np.c_[np.full(SAMPLES[1], x[end, 0]), r[end] * np.sin(theta[0]),
                     r[end] * np.cos(theta[0])]
        cap = pv.PolyData(ring, np.r_[len(ring), np.arange(len(ring))]).triangulate()
        caps.append(cap)
    return surface, caps


def frame(job):
    out, index, total = job
    target = Path(out) / f"frame_{index:05d}.png"
    if target.exists():
        return
    t = index / (total - 1)
    front = -0.3 + (SPAN + 0.6) * float(ramp(t, *CARVE))
    camera, angle = camera_at(t)
    plot = new_plot(SIZE, camera, angle)
    surface, caps = body(front)
    plot.add_mesh(surface, scalars="rgb", rgb=True, smooth_shading=True, specular=0.45,
                  specular_power=30, ambient=0.18)
    for cap in caps:
        plot.add_mesh(cap, color=tuple(BODY_COLOUR), ambient=0.25)
    if 0 <= front <= SPAN:
        for k in range(GROOVES):
            a = groove_angle(front, k)
            where = (front, RADIUS * np.sin(a), RADIUS * np.cos(a))
            plot.add_mesh(pv.Sphere(radius=0.06, center=where), color=CUTTER_COLOUR,
                          lighting=False)
            plot.add_mesh(pv.Sphere(radius=0.16, center=where), color=CUTTER_COLOUR,
                          opacity=0.25, lighting=False)
    plot.screenshot(str(target))
    plot.close()


def anchors(total):
    """Screen positions of chosen points at chosen moments, for captions and arrows."""
    points = {"carved_x2": lambda: (2.0, RADIUS * np.sin(groove_angle(2.0, 1)),
                                    RADIUS * np.cos(groove_angle(2.0, 1))),
              "groove_mid": lambda: (6.0, RADIUS * np.sin(groove_angle(6.0, 1)),
                                     RADIUS * np.cos(groove_angle(6.0, 1))),
              "body_mid": lambda: CENTRE}
    for t in (0.1, 0.45, 0.6, 0.8, 1.0):
        camera, angle = camera_at(t)
        plot = new_plot(SIZE, camera, angle)
        plot.add_mesh(pv.Sphere(radius=0.01))
        plot.render()
        ren = plot.renderer
        found = []
        for name, point in points.items():
            ren.SetWorldPoint(*point(), 1)
            ren.WorldToDisplay()
            x, y, _ = ren.GetDisplayPoint()
            found.append(f"{name} ({round(x)}, {round(SIZE[1] - y)})")
        print(f"t = {t * total / 24:.1f} s: " + ", ".join(found))
        plot.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out")
    parser.add_argument("--frames", type=int, default=288)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--anchors", action="store_true")
    args = parser.parse_args()
    if args.anchors:
        anchors(args.frames)
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(str(out), i, args.frames) for i in range(args.frames)]
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(frame, jobs))
    print(f"{out}: {args.frames} frames")


if __name__ == "__main__":
    main()
