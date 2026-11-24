"""Draw frames 0, 12 and 23 of shots/marker_layers.yml.

Needs no data: its tag, cylinder, is a body made in code (data/cylinder/domain.yml).

Pictures go to ./marker_layers_<frame>.png.
"""
from pathlib import Path

from PIL import Image

from flowreel.scene import render_frame
from flowreel.scene.shot import load

if __name__ == "__main__":
    shot = load(Path(__file__).parent / "shots" / "marker_layers.yml")   # its tag: data/cylinder/
    for frame in (0, 12, 23):
        Image.fromarray(render_frame(shot, frame)).save(f"marker_layers_{frame}.png")
