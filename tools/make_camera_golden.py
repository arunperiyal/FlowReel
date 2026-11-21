"""Draw Phase 6's golden frames from tests/data/camera/session.yml, without FlowReel's
camera code.

Usage: python tools/make_camera_golden.py [--out tests/data/camera]

The camera editor has no counterpart in the prototype, so the goldens are drawn here by
plain pyvista and Pillow from the numbers in ``session.yml``, the same numbers the
scripted editor session in ``tests/test_golden_camera.py`` picks in the window. Nothing
of FlowReel's views, tracks, projection, captions or file writing is used; only the body
(``grooved_cylinder``, the geometry source's) and the drawing options of the
``geometry`` layer, copied here as plain ``add_mesh`` arguments.

- ``golden_key.png``: the body seen from key ``golden.key``'s view.
- ``golden_mid.png``: from the view halfway between keys 0 and 12, blended here: at the
  middle of a ``smooth`` segment the eased fraction is 3t^2 - 2t^3 = 0.5, so position,
  focal point, up and view angle are the averages of the two keys'.
- ``arrow_NNNNN.png``: the anchored arrow alone (transparent), from ``arrow.from`` in
  pixels to ``arrow.to`` in the model, projected by VTK's own camera transform
  (``WorldToView``) for each frame's view, drawn as FlowReel draws an arrow: a line and a
  filled head 4.5 widths long and half as wide.

Golden frames are drawn in software by OSMesa (see make_carve_golden.py). Not part of the
package. Run it again only to change the golden frames on purpose.
"""
import argparse
import os

os.environ["VTK_DEFAULT_OPENGL_WINDOW"] = "vtkOSOpenGLRenderWindow"
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent


def smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def view_at(keys: list[dict], frame: float) -> dict:
    """The view at ``frame`` between the two keys around it, eased by smoothstep."""
    for a, b in zip(keys, keys[1:]):
        if a["frame"] <= frame <= b["frame"]:
            t = smooth((frame - a["frame"]) / (b["frame"] - a["frame"]))
            mix = lambda p, q: (np.asarray(p, float) + (np.asarray(q, float) - np.asarray(p, float)) * t)
            return {"position": mix(a["position"], b["position"]), "focal": mix(a["focal"], b["focal"]),
                    "up": mix(a["up"], b["up"]),
                    "view_angle": a["view_angle"] + (b["view_angle"] - a["view_angle"]) * t}
    raise ValueError(f"frame {frame} is outside the keys")


def plotter(session: dict, view: dict):
    import pyvista as pv
    from flowreel.sources.bodies import grooved_cylinder
    p = pv.Plotter(off_screen=True, window_size=list(session["size"]))
    p.set_background("black")
    cam = p.camera
    cam.position, cam.focal_point, cam.up = (tuple(map(float, view[k])) for k in
                                             ("position", "focal", "up"))
    cam.view_angle = float(view["view_angle"])
    b = session["body"]
    p.add_mesh(grooved_cylinder(), color=b["colour"], smooth_shading=True, split_sharp_edges=True,
               opacity=1.0, specular=b["specular"], specular_power=b["specular_power"],
               ambient=b["ambient"])
    return p


def frame(session: dict, view: dict) -> np.ndarray:
    p = plotter(session, view)
    try:
        return np.asarray(p.screenshot(return_img=True))[:, :, :3]
    finally:
        p.close()


def tip(session: dict, view: dict) -> tuple[float, float]:
    """The arrow's tip in pixels (y down), by VTK's own world-to-view transform."""
    p = plotter(session, view)
    try:
        p.render()
        ren = p.renderer
        ren.SetWorldPoint(*map(float, session["arrow"]["to"]), 1.0)
        ren.WorldToView()
        vx, vy, _ = ren.GetViewPoint()
    finally:
        p.close()
    w, h = session["size"]
    return ((vx + 1) / 2 * w, (1 - vy) / 2 * h)


def arrow(session: dict, end: tuple[float, float]):
    from PIL import Image, ImageDraw, ImageColor
    a = session["arrow"]
    image = Image.new("RGBA", tuple(session["size"]), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colour = ImageColor.getrgb(a["colour"]) + (255,)
    start, end = complex(*a["from"]), complex(*end)
    along = (end - start) / abs(end - start)
    width = float(a["width"])
    head = 4.5 * width
    base = end - head * along
    side = along * 1j * head * 0.5
    xy = lambda z: (z.real, z.imag)
    draw.line([xy(start), xy(base)], fill=colour, width=round(width))
    draw.polygon([xy(end), xy(base + side), xy(base - side)], fill=colour)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "camera")
    args = parser.parse_args()
    from PIL import Image
    session = yaml.safe_load((args.out / "session.yml").read_text())
    keys = session["keys"]
    g = session["golden"]
    for name, f in (("golden_key", g["key"]), ("golden_mid", g["mid"])):
        Image.fromarray(frame(session, view_at(keys, f))).save(args.out / f"{name}.png")
        print(f"{args.out / name}.png: frame {f}")
    for f in session["arrow"]["frames"]:
        end = tip(session, view_at(keys, f))
        arrow(session, end).save(args.out / f"arrow_{f:05d}.png")
        print(f"{args.out}/arrow_{f:05d}.png: frame {f}, tip at ({end[0]:.2f}, {end[1]:.2f})")


if __name__ == "__main__":
    main()
