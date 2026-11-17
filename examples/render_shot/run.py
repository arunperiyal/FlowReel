"""Render shot.yml to ./frames, then a half-size draft, then measure one frame.

Needs no data: the flow is a solid-body vortex u = (-y, x, 0) made here, the body a
sphere. Frames go to ./frames/render_shot/ and ./frames/render_shot@320x180/. Run it
twice: the second run skips every frame, because no frame's key changed.
"""
from pathlib import Path

import pyvista as pv

from flowreel.box import Box
from flowreel.scene import render
from flowreel.scene.memory import measure

HERE = Path(__file__).parent


class Vortex:
    """A source with one step. Defined at module level so worker processes can load it."""

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

    def bounds(self):
        return Box((-1, -1, 0), (1, 1, 1))

    def memory_per_step(self, crop):
        return 17 * 17 * 9 * 8 * 8 / 1024 ** 3


def report(r):
    print(f"{r.folder}: {r.count('rendered')} drawn, {r.count('skipped')} skipped "
          f"(backend {r.backend})")


if __name__ == "__main__":
    shot = HERE / "shot.yml"
    report(render(shot, source=Vortex(), out="frames", jobs=2))
    report(render(shot, source=Vortex(), out="frames", jobs=2, scale=0.5))
    print(measure(shot, source=Vortex()).text())
