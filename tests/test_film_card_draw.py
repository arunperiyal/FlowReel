"""Cards drawn (film/cards.py): blocks centred by measured width, colours, scaling."""
import numpy as np
import pytest
from PIL import Image

from flowreel.film.cards import card_from_dict, card_image
from flowreel.film.schema import FilmStyle

STYLE = FilmStyle(text="#ffffff", muted="#808080")


def card(tmp_path, *blocks, **top):
    return card_from_dict({"blocks": list(blocks), "size": [400, 300], **top},
                          file=str(tmp_path / "card.yml"))


def ink(a, rows=slice(None)):
    """Columns and rows of lit pixels in rows ``rows`` of an RGB array."""
    lit = a[rows].max(axis=2) > 40
    ys, xs = np.nonzero(lit)
    return xs.min(), xs.max() + 1, ys.min(), ys.max() + 1


def test_text_is_centred_by_its_measured_width(tmp_path):
    a = np.asarray(card_image(card(tmp_path, {"title": ["A wide line of text", "Short"],
                                              "size": 30, "y": 50}), STYLE))
    for rows in (slice(40, 90), slice(90, 140)):
        left, right, _, _ = ink(a, rows)
        assert abs((left + right) / 2 - 200) <= 2


def test_default_colours_are_the_films(tmp_path):
    a = np.asarray(card_image(card(tmp_path, {"title": "TITLE", "size": 40, "y": 20},
                                   {"divider": 200, "thickness": 4, "y": 120},
                                   {"heading": "BY", "names": ["NAME"], "y": 160}), STYLE))
    assert tuple(a[30:70].reshape(-1, 3).max(axis=0)) == (255, 255, 255)   # title: text
    assert tuple(a[121, 200]) == (128, 128, 128)                           # divider: muted
    assert a[121, 99].max() == 0 and tuple(a[121, 101]) == (128, 128, 128)
    assert tuple(a[160:190].reshape(-1, 3).max(axis=0)) == (128, 128, 128) # heading: muted
    assert tuple(a[205:250].reshape(-1, 3).max(axis=0)) == (255, 255, 255) # names: text


def test_a_colour_and_a_background(tmp_path):
    a = np.asarray(card_image(card(tmp_path, {"text": "x", "colour": "#ff0000", "size": 40,
                                              "y": 100}, background="#102030"), STYLE))
    assert tuple(a[5, 5]) == (16, 32, 48)
    assert tuple(a[100:150].reshape(-1, 3).max(axis=0)) == (255, 32, 48)


def test_an_image_is_scaled_and_centred_with_its_transparency(tmp_path):
    logo = Image.new("RGBA", (40, 20), (0, 255, 0, 255))
    logo.paste((0, 0, 0, 0), (0, 0, 20, 20))                 # left half transparent
    logo.save(tmp_path / "logo.png")
    a = np.asarray(card_image(card(tmp_path, {"image": "logo.png", "height": 40, "y": 10}), STYLE))
    green = (a[..., 1] > 200) & (a[..., 0] < 50)
    ys, xs = np.nonzero(green)
    assert (xs.min(), xs.max() + 1, ys.min(), ys.max() + 1) == (200, 240, 10, 50)


def test_a_background_image_covers_the_card(tmp_path):
    Image.new("RGB", (100, 100), (0, 0, 255)).save(tmp_path / "back.png")
    a = np.asarray(card_image(card(tmp_path, {"text": "x", "y": 0}, background_image="back.png"),
                              STYLE))
    assert tuple(a[0, 0]) == tuple(a[299, 399]) == (0, 0, 255)


def test_another_size_scales_the_whole_card(tmp_path):
    c = card(tmp_path, {"divider": 200, "thickness": 4, "y": 150})
    a = np.asarray(card_image(c, STYLE, size=(200, 150)))
    assert a.shape == (150, 200, 3)
    assert a[75, 100].max() > 100 and a[75, 30].max() == 0 and a[20, 100].max() == 0


def test_without_a_style_the_film_defaults(tmp_path):
    a = np.asarray(card_image(card(tmp_path, {"title": "T", "size": 60, "y": 50})))
    assert tuple(a.reshape(-1, 3).max(axis=0)) == (0xf2, 0xf2, 0xf2)


def test_a_card_in_another_installed_font():
    """style.font reaches the card: DejaVu Serif (matplotlib's own) draws other pixels than
    Lato, and a font that is not installed is an error naming it."""
    from dataclasses import replace as _replace
    card = card_from_dict({"blocks": [{"title": ["Flow past a cylinder"], "y": 100},
                                      {"heading": "BY", "names": ["A. Author"], "gap": 20}]})
    lato = np.asarray(card_image(card, FilmStyle()))
    serif = np.asarray(card_image(card, _replace(FilmStyle(), font="DejaVu Serif")))
    assert (lato != serif).any() and serif.max() > 200
    with pytest.raises(ValueError, match="'No Such Font' is not installed"):
        card_image(card, _replace(FilmStyle(), font="No Such Font"))
