"""Draw every support symbol, one panel each, into one picture.

Usage: python run.py [OUT.png]   (default ./supports.png)

Needs no data: the body is a beam 6 diameters long made here, declared in code (as a tag's
domain.yml would declare it) with one end of each kind. docs/images/supports.png is
this script's output.
"""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw, ImageFont

import flowreel
from flowreel.box import Box
from flowreel.project.bodies import Body, End
from flowreel.project.names import DeclaredSource
from flowreel.scene import render_frame
from flowreel.scene.shot import from_dict
from flowreel.scene.views import parse_view

PANEL = (480, 300)
KINDS = [
    ("clamped", {}, False),
    ("pinned", {}, False),
    ("roller", {"free_along": "x"}, True),
    ("spring", {"stiffness": 10.0}, False),
    ("free", {"mark": True}, False),
    ("prescribed", {"direction": "y"}, False),
]


class Beam:
    """A source with one step and one body: a cylinder of diameter 1 along x, 0 to 6."""

    name = "beam"

    def steps(self):
        return [0]

    def time(self, step):
        return 0.0

    def fields(self):
        return []

    def bodies(self):
        return ["beam"]

    def body(self, step, name=None):
        return pv.Cylinder(center=(3, 0, 0), direction=(1, 0, 0), radius=0.5, height=6,
                           resolution=48).triangulate()

    def bounds(self):
        return Box((0, -3, -2), (6, 1, 2))

    def series(self, name):
        raise KeyError(name)

    def memory_per_step(self, crop):
        return 0.0


def panel(kind: str, options: dict, tension: bool) -> np.ndarray:
    body = Body("beam", "beam", axis="x", diameter=1.0,
                ends=(End(0.0, kind, tension, options),))
    source = DeclaredSource(Beam(), {"beam": body})
    shot = from_dict({"name": kind, "source": "beam", "time": {"frozen": 0, "frames": 1},
                      "camera": {"view": "v"}, "size": list(PANEL), "lights": "raking",
                      "layers": [{"type": "body", "colour": "#c8ccd0"},
                                 {"type": "supports", "colour": "#e0a030"}]})
    view = parse_view({"name": "v", "position": [-6.5, 2.5, 7.5], "focal": [0.6, -0.9, 0],
                       "up": [0, 1, 0], "view_angle": 30})
    return render_frame(shot, 0, source, views={"v": view})


def main(out: Path) -> None:
    font = ImageFont.truetype(str(Path(flowreel.__file__).parent / "fonts" / "Lato-Regular.ttf"), 22)
    sheet = Image.new("RGB", (PANEL[0] * 3, PANEL[1] * 2))
    for i, (kind, options, tension) in enumerate(KINDS):
        tile = Image.fromarray(panel(kind, options, tension))
        label = kind + (" + tension" if tension else "")
        ImageDraw.Draw(tile).text((16, 12), label, font=font, fill=(235, 235, 235))
        sheet.paste(tile, ((i % 3) * PANEL[0], (i // 3) * PANEL[1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    print(f"{out}: {len(KINDS)} symbols")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("supports.png"))
