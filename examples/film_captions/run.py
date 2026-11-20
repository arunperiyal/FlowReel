"""Draw a film's captions, their shapes and a watermark over a generated picture.

Usage: python run.py [DIR]   (default ./film_captions_example)

Needs no data. It reads text/captions.yml (places, a box and a shadow, maths, every 2D
shape), draws each caption as a transparent PNG the size of the film, as the film build
lays them over a shot, and a still with all of them and a text watermark over a
generated wake, to look at. Prints each caption's measured text box.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from flowreel.film.draw import caption_image
from flowreel.film.schema import FilmStyle, parse_watermark
from flowreel.film.text import load_text
from flowreel.film.watermark import watermark_image
from flowreel.scene.errors import Checker

HERE = Path(__file__).parent
SIZE = (1920, 1080)


def background() -> Image.Image:
    """A dark blue picture with a generated wake: alternating light and dark rings."""
    y, x = np.mgrid[0:SIZE[1], 0:SIZE[0]].astype(float)
    wake = np.sin((x - 960) / 70) * np.exp(-((y - 560) / 140) ** 2) * (x > 960)
    picture = np.stack([20 + 90 * wake.clip(0), 40 + 40 * np.abs(wake), 70 + 90 * (-wake).clip(0)], -1)
    return Image.fromarray(picture.clip(0, 255).astype(np.uint8)).convert("RGBA")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    style = FilmStyle()
    still = background()
    for c in load_text(HERE / "text" / "captions.yml"):
        image, block = caption_image(c, style, SIZE)
        image.save(folder / f"caption_{c.id}.png")
        still = Image.alpha_composite(still, image)
        left, top, right, bottom = block.box
        print(f"{c.id:7s} text from ({left:.0f}, {top:.0f}) to ({right:.0f}, {bottom:.0f})")
    mark = parse_watermark({"text": "FlowReel example", "size": 28, "opacity": 0.6},
                           Checker("run.py"), HERE)
    still = Image.alpha_composite(still, watermark_image(mark, SIZE))
    still.convert("RGB").save(folder / "still.png")
    print(f"wrote {folder / 'still.png'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_captions_example"))
