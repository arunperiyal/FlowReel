"""Draw a card from its file: a logo, a title, a divider, names and small print.

Usage: python run.py [DIR]   (default ./film_cards_example)

Needs no data. It writes a generated logo next to a copy of card.yml in DIR, prints
where each block falls (top and bottom, in pixels), and draws the card at full size
(card.png) and at a preview size (card_480p.png).
"""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from flowreel.film.cards import card_image, layout, load_card

HERE = Path(__file__).parent


def make_logo(path: Path) -> None:
    """A generated logo: a ring and a bar on transparency."""
    logo = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    draw.ellipse((60, 10, 340, 290), outline=(255, 255, 255, 255), width=28)
    draw.rectangle((20, 130, 380, 170), fill=(230, 160, 60, 255))
    logo.save(path)


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "card.yml", folder / "card.yml")
    make_logo(folder / "logo.png")
    card = load_card(folder / "card.yml")
    for block, (top, bottom) in zip(card.blocks, layout(card)):
        print(f"{block.kind:8s} {top:5.0f} to {bottom:5.0f}")
    card_image(card).save(folder / "card.png")
    card_image(card, size=(854, 480)).save(folder / "card_480p.png")
    print(f"wrote {folder / 'card.png'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_cards_example"))
