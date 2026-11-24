"""Draw a scene of text, a logo, a divider and shapes over a generated picture.

Usage: python run.py [DIR]   (default ./text_boxes_example)

Needs no data. It makes DIR a project, writes a generated picture (a wake of light and
dark rings) and a generated logo into DIR/assets (a real film's logo stays outside the
repository), copies film.yml and layouts/text_boxes.yml, and draws a still of the scene
into DIR/frames/scenes/text_boxes/ with ``scene preview``. The layout shows what a box
can be: a title with a divider, a caption with maths, a text in a box, an arrow, a
circle, an ellipse and a rounded rectangle.
"""
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from tag_project import flowreel  # noqa: E402

SIZE = (1920, 1080)


def make_picture(path: Path) -> None:
    """A dark blue picture with a generated wake: alternating light and dark rings."""
    y, x = np.mgrid[0:SIZE[1], 0:SIZE[0]].astype(float)
    wake = np.sin((x - 960) / 70) * np.exp(-((y - 560) / 140) ** 2) * (x > 960)
    picture = np.stack([20 + 90 * wake.clip(0), 40 + 40 * np.abs(wake), 70 + 90 * (-wake).clip(0)], -1)
    Image.fromarray(picture.clip(0, 255).astype(np.uint8)).save(path)


def make_logo(path: Path) -> None:
    """A generated logo: a ring and a bar on transparency."""
    logo = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    draw.ellipse((60, 10, 340, 290), outline=(255, 255, 255, 255), width=28)
    draw.rectangle((20, 130, 380, 170), fill=(230, 160, 60, 255))
    logo.save(path)


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    flowreel(folder, "project", "init", "--force")
    (folder / "assets").mkdir(exist_ok=True)
    make_picture(folder / "assets" / "wake.png")
    make_logo(folder / "assets" / "logo.png")
    shutil.copytree(HERE / "layouts", folder / "layouts", dirs_exist_ok=True)
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    out = flowreel(folder, "scene", "preview", "text_boxes", "--at", "0.5").strip().splitlines()[-1]
    print(re.sub(r" in [\d.]+ s", "", out).replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("text_boxes_example"))
