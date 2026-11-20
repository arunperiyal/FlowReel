"""Draw the golden opening card with the prototype's ``make_film.opening_card``.

Usage: python tools/make_card_golden.py [--out tests/data/cards]

The AFMS film's opening card, drawn by the prototype's own function: a logo, a title of
two lines, a divider and two groups of names. Its logo is replaced by a generated one
(``logo.png``: a ring and a bar on transparency, written here; no logos in the
repository), and its names by placeholders. Its fonts are the Lato files bundled with
FlowReel (the prototype found them installed; the files are the same).

The same card written for FlowReel is ``tests/data/cards/opening.yml``;
``tests/test_golden_card.py`` draws it and compares.

Not part of the package. Run it again only to change the golden card on purpose.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = {"title": ["Effect of Helical Grooves on Suppression of",
                  "Vortex-Induced Vibration in Flexible Cylinders"],
        "created_by": ["A. Author"],
        "coauthors": ["B. Author, C. Author,", "D. Author and E. Author"]}


def make_logo(path: Path) -> None:
    """A white ring with a bar through it, on transparency, 400 x 300."""
    from PIL import Image, ImageDraw
    logo = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    draw.ellipse((60, 10, 340, 290), outline=(255, 255, 255, 255), width=28)
    draw.rectangle((20, 130, 380, 170), fill=(230, 160, 60, 255))
    logo.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "cards")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import make_film

    from flowreel.scene.text import font_file
    args.out.mkdir(parents=True, exist_ok=True)
    make_logo(args.out / "logo.png")
    make_film.LOGO = args.out / "logo.png"
    make_film.FONT, make_film.FONT_LIGHT = font_file("Regular"), font_file("Light")
    make_film.opening_card(args.out / "opening.png", TEXT)
    print(args.out / "opening.png")


if __name__ == "__main__":
    main()
