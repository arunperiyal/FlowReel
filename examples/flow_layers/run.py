"""Draw frames 0, 12 and 23 of shot.yml from a generated solid-body vortex.

Needs no data: the flow is u = (-y, x, 0) on a small grid, the body a sphere. Run it
from anywhere; pictures go to ./flow_layers_<frame>.png. The data is made up here
(the same toy used by the tests); with real output you would give the shot a
``vtk:`` or ``flexflow:`` source instead.
"""
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image

from flowreel.scene import render_frame
from flowreel.scene.shot import load


class Vortex:
    name = "vortex"

    def steps(self):
        return [0]

    def time(self, step):
        return 0.0

    def flow(self, step, fields, crop):
        grid = pv.ImageData(dimensions=(17, 17, 9), spacing=(0.125, 0.125, 0.125),
                            origin=(-1, -1, 0)).cast_to_unstructured_grid()
        x, y = grid.points[:, 0], grid.points[:, 1]
        for name, value in {"U": -y, "V": x, "W": 0 * x}.items():
            grid.point_data[name] = value
        return grid

    def body(self, step, name=None):
        return pv.Sphere(radius=0.2, center=(0, 0, 0.5))


if __name__ == "__main__":
    shot = load(Path(__file__).with_name("shot.yml"))
    for frame in (0, 12, 23):
        Image.fromarray(render_frame(shot, frame, Vortex())).save(f"flow_layers_{frame}.png")
