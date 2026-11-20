"""Branch 3's check: the opening card drawn by FlowReel from a card file matches the one
drawn by the prototype's own ``make_film.opening_card`` (``tools/make_card_golden.py``),
its logo replaced by a generated one.

Compared over the whole card with the limits of Phase 2's golden tests. A card whose
title lines are a few pixels further apart must fail the same limits.

The golden card was drawn by a Pillow without raqm, so unkerned; FlowReel kerns where
Pillow can, so here it is drawn unkerned too, on any machine.
"""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.film.cards import card_image, load_card
from flowreel.film.schema import FilmStyle
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

DATA = Path(__file__).parent / "data" / "cards"


@pytest.fixture(autouse=True)
def unkerned(monkeypatch):
    """Lay text out as the golden card's Pillow did: no raqm, so no kerning."""
    from PIL import features
    check = features.check
    monkeypatch.setattr(features, "check", lambda name: False if name == "raqm" else check(name))


@pytest.fixture(scope="module")
def gold():
    return np.asarray(Image.open(DATA / "opening.png").convert("RGB"))


def test_the_opening_card_matches_the_prototypes(gold):
    picture = np.asarray(card_image(load_card(DATA / "opening.yml"), FilmStyle()))
    assert picture.shape == gold.shape == (1080, 1920, 3)
    mean, clear = difference(picture, gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


def test_a_nearby_card_fails(gold):
    card = load_card(DATA / "opening.yml")
    title = card.blocks[1]
    card.blocks[1] = replace(title, keys={**title.keys, "spacing": 88})
    mean, clear = difference(np.asarray(card_image(card, FilmStyle())), gold)
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (mean, clear)
