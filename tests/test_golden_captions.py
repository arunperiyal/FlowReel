"""Branch 2's check: captions drawn by FlowReel match pictures drawn by the prototype's
own ``make_film.caption_image`` (``tools/make_caption_golden.py``): a boxed caption
with maths and an arrow, and a shadowed one in a colour with two wide arrows.

Both are laid on a mid-grey picture, so the shadow and the box count, and compared
inside the golden caption's own extent (padded), with the limits of Phase 2's golden
tests. A caption moved by a few pixels must fail the same limits, or the check proves
nothing.
"""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.film.draw import caption_image
from flowreel.film.schema import FilmStyle
from flowreel.film.text import load_text
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

DATA = Path(__file__).parent / "data" / "captions"
PICTURE = (1920, 1080)
GREY = (90, 110, 130, 255)
PAD = 20


def seen(image):
    """``image`` (RGBA) over mid-grey, as an RGB array."""
    return np.asarray(Image.alpha_composite(Image.new("RGBA", image.size, GREY), image).convert("RGB"))


@pytest.fixture(scope="module")
def captions():
    return {c.id: c for c in load_text(DATA / "text.yml")}


def compare(picture, gold_image):
    """The difference inside the golden caption's extent, padded."""
    ys, xs = np.nonzero(np.asarray(gold_image)[..., 3])
    top, bottom = max(0, ys.min() - PAD), ys.max() + PAD
    left, right = max(0, xs.min() - PAD), xs.max() + PAD
    gold = seen(gold_image)
    return difference(picture[top:bottom, left:right], gold[top:bottom, left:right])


@pytest.mark.parametrize("name", ["boxed", "shadow"])
def test_a_caption_matches_the_prototypes(captions, name):
    gold = Image.open(DATA / f"{name}.png").convert("RGBA")
    image, _ = caption_image(captions[name], FilmStyle(), PICTURE)
    assert image.size == gold.size == PICTURE
    mean, clear = compare(seen(image), gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


@pytest.mark.parametrize("name, place", [("boxed", (704, 123)), ("shadow", ("centre", 900))])
def test_a_nearby_caption_fails(captions, name, place):
    gold = Image.open(DATA / f"{name}.png").convert("RGBA")
    image, _ = caption_image(replace(captions[name], place=place), FilmStyle(), PICTURE)
    mean, clear = compare(seen(image), gold)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (mean, clear)
