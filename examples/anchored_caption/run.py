"""Render a panning shot, then build a film whose caption follows the body.

Usage: python run.py [DIR]   (default ./anchored_caption_example)

Needs no data, only off-screen rendering and ffmpeg. It renders shot.yml (a sphere, the
camera panning round it) to DIR/frames/anchored/, where shot render also records each
frame's camera (.views.json). It then builds DIR/film.mp4 from film.yml: a caption, an
arrow, a label and a dimension, all given as points of the model, drawn where those
points are on every frame. Prints where the top of the sphere (the arrow's tip) lands
in the film at the start, middle and end, and any stretch where a point is hidden. Run
it twice: the second run draws nothing and keeps every clip.
"""
import shutil
import sys
from pathlib import Path

import pyvista as pv

from flowreel import film
from flowreel.box import Box
from flowreel.film.anchors import Anchor, ShotProjector, hidden_spans
from flowreel.film.build import build
from flowreel.film.clips import Clips
from flowreel.scene import render

HERE = Path(__file__).parent


class Vortex:
    """A source with one step: a solid-body vortex round a sphere. At module level so
    worker processes can load it."""

    name = "vortex"

    def steps(self):
        return [0]

    def time(self, step):
        return 0.0

    def flow(self, step, fields, crop):
        grid = pv.ImageData(dimensions=(9, 9, 5), spacing=(0.25, 0.25, 0.25),
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
        return 9 * 9 * 5 * 8 * 8 / 1024 ** 3


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("shot.yml", "cameras.yml", "film.yml"):
        shutil.copy(HERE / name, folder / name)
    report = render(folder / "shot.yml", source=Vortex(), out=folder / "frames", jobs=2)
    print(f"rendered {report.count('rendered')} frames, {report.count('skipped')} kept")
    built = build(folder / "film.yml")
    print(f"built {built.output.relative_to(folder)}")
    clips = Clips(film.load(folder / "film.yml"))
    projector = ShotProjector(clips.film, clips.line, "pan")
    last = round(clips.line.shot("pan").length * clips.film.fps) - 1
    for j in (0, last // 2, last):
        x, y = projector.point(Anchor((0, 0, 0.72)), j)
        print(f"frame {j:2d}: top of the sphere at ({x:.0f}, {y:.0f})")
    for hidden in hidden_spans(clips):
        print("hidden:", hidden.message())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("anchored_caption_example"))
