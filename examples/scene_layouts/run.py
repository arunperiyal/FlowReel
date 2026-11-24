"""Layouts of boxes: frame folders side by side and on a grid, as scenes of a film.

Usage: python run.py [DIR]   (default ./scene_layouts_example)

Needs no data. It draws three small frame folders with PIL (DIR/frames/bare and
DIR/frames/helical, eight frames of a moving dot; DIR/frames/title, one frame), makes DIR
a project, and copies film.yml and layouts/ into it. Then:

1. layouts/compare.yml, the scene ``compare``: bare and helical side by side, labelled
   by text boxes.
2. layouts/grid.yml, the scene ``grid``: four boxes on a 2 x 2 grid, one an image.
3. ``film lengths`` plans the two scenes; ``scene preview`` draws a still of each
   (DIR/frames/scenes/compare/, DIR/frames/scenes/grid/).
"""
import math
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from tag_project import flowreel  # noqa: E402


def draw_frames(folder: Path, colour: str, wobble: float, n: int = 8) -> None:
    """``n`` frames of a dot going round, 480 x 270."""
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        im = Image.new("RGB", (480, 270), "#1b2630")
        d = ImageDraw.Draw(im)
        x = 240 + 150 * math.cos(2 * math.pi * i / n)
        y = 135 + wobble * math.sin(2 * math.pi * i / n)
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=colour)
        im.save(folder / f"frame_{i:05d}.png")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    flowreel(folder, "project", "init", "--force")
    shutil.copytree(HERE / "layouts", folder / "layouts", dirs_exist_ok=True)
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    frames = folder / "frames"
    draw_frames(frames / "bare", "#e8b04a", 80)
    draw_frames(frames / "helical", "#6ac1c8", 10)
    draw_frames(frames / "title", "#ffffff", 0, n=1)
    print(flowreel(folder, "film", "lengths").strip())
    for scene in ("compare", "grid"):
        out = flowreel(folder, "scene", "preview", scene, "--at", "0.5").strip().splitlines()[-1]
        print(re.sub(r" in [\d.]+ s", "", out).replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scene_layouts_example"))
