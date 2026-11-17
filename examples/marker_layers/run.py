"""Draw frames 0, 12 and 23 of shot.yml. Needs no data: the body is built in code.

Pictures go to ./marker_layers_<frame>.png.
"""
from pathlib import Path

from PIL import Image

from flowreel.scene import render_frame
from flowreel.scene.shot import load
from flowreel.sources.geometry import GeometrySource

if __name__ == "__main__":
    shot = load(Path(__file__).with_name("shot.yml"))
    source = GeometrySource("grooved_cylinder", params={"span": 6, "samples": (81, 161)})
    for frame in (0, 12, 23):
        Image.fromarray(render_frame(shot, frame, source)).save(f"marker_layers_{frame}.png")
