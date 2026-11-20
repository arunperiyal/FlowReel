"""Draw the golden caption pictures with the prototype's ``make_film.caption_image``.

Usage: python tools/make_caption_golden.py [--out tests/data/captions]

Two captions, as the AFMS film wrote them in ``film_text.toml``:

- ``boxed.png``: two left-aligned lines with maths at ``[x, y]``, a dark box, an arrow;
- ``shadow.png``: two centred lines with maths at the bottom, a soft shadow, two arrows
  of width 6, in a colour of their own.

The same captions written for FlowReel are ``tests/data/captions/text.yml``;
``tests/test_golden_captions.py`` draws them and compares. Lato is the copy bundled
with FlowReel, registered with matplotlib first (the prototype found it installed).

Not part of the package. Run it again only to change the golden pictures on purpose.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CAPTIONS = {
    "boxed": {"lines": ["Each groove $0.08D$ deep and $0.2D$ wide,",
                        "rms $C_L$ falls by $60\\%$"],
              "place": [700, 120], "size": 40, "align": "left", "box": True,
              "arrows": [[1250, 230, 1420, 420]]},
    "shadow": {"lines": ["Lift along the span, $C_L(x/D, tU/D)$",
                         "the cells of the smooth cylinder break up"],
               "place": "bottom", "colour": "#f5a142", "arrow_width": 6,
               "arrows": [[640, 850, 480, 640], [1280, 850, 1440, 640]]},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "captions")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    from flowreel.compose.style import register_fonts
    register_fonts()
    import make_film
    args.out.mkdir(parents=True, exist_ok=True)
    for name, caption in CAPTIONS.items():
        path = args.out / f"{name}.png"
        make_film.caption_image(caption, path)
        print(path)


if __name__ == "__main__":
    main()
