"""Captions drawn (film/draw.py): measured places, alignment, shadow or box, shapes."""
import numpy as np
import pytest

from flowreel.film.draw import caption_image, look, text_block
from flowreel.film.schema import CaptionStyle, FilmStyle
from flowreel.film.text import parse_caption
from flowreel.scene.errors import Checker

PICTURE = (640, 360)
STYLE = FilmStyle(caption=CaptionStyle(size=30, margin=20))


def cap(**spec):
    return parse_caption({"lines": ["Wake behind", "the cylinder"], **spec}, Checker(None))


def alpha(c, style=STYLE):
    image, block = caption_image(c, style, PICTURE)
    assert image.size == PICTURE and image.mode == "RGBA"
    return np.asarray(image)[..., 3], block


def ink(a, level=200):
    """The box (left, top, right, bottom) of nearly opaque pixels."""
    ys, xs = np.nonzero(a > level)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def test_the_look_fills_gaps_from_the_style():
    lk = look(cap(size=12, box=True), STYLE)
    assert (lk.size, lk.box, lk.shadow, lk.colour, lk.align) == (12, True, True, "#f2f2f2", "centre")
    assert look(cap(colour="#ff0000", align="left"), STYLE).colour == "#ff0000"


@pytest.mark.parametrize("place, check", [
    ("top", lambda b: b.box[1] == 20),
    ("bottom", lambda b: b.box[3] == 360 - 20),
    ("centre", lambda b: b.box[1] + b.box[3] == 360),
    ([100, 50], lambda b: b.box[:2] == (100, 50)),
    (["centre", 50], lambda b: b.box[1] == 50),
])
def test_places(place, check):
    b = text_block(cap(place=place), STYLE, PICTURE)
    assert check(b), b
    assert b.box[3] - b.box[1] == 2 * round(30 * 1.3)          # two lines, 1.3 apart
    if place != [100, 50]:
        assert b.box[0] + b.box[2] == pytest.approx(640)       # centred across


def test_the_text_falls_inside_its_measured_block():
    a, b = alpha(cap(place="centre", shadow=False))
    left, top, right, bottom = ink(a)
    assert b.box[0] - 2 <= left and right <= b.box[2] + 2
    assert b.box[1] - 2 <= top and bottom <= b.box[3] + 2
    assert right - left > 0.9 * (b.box[2] - b.box[0])           # and fills its width


@pytest.mark.parametrize("align", ["left", "centre", "right"])
def test_lines_are_aligned_by_their_measured_widths(align):
    b = text_block(cap(align=align, place=[100, 50]), STYLE, PICTURE)
    left, _, right, _ = b.box
    assert b.widths[0] != b.widths[1] and right - left == max(b.widths)
    for (x, _), w in zip(b.lines, b.widths):
        if align == "left":
            assert x == left
        elif align == "centre":
            assert x + w / 2 == pytest.approx((left + right) / 2)
        else:
            assert x + w == pytest.approx(right)


def test_a_shadow_spreads_around_the_text_and_a_box_takes_its_place():
    plain, _ = alpha(cap(place="centre", shadow=False))
    shadow, _ = alpha(cap(place="centre"))
    boxed, b = alpha(cap(place="centre", box=True))
    assert (shadow > 0).sum() > 2 * (plain > 0).sum()
    assert (shadow >= plain).all()
    left, top, right, bottom = b.box
    pad = round(30 * 0.6)
    assert boxed[int(top), int(left - pad / 2)] == 175           # the box, inside its pad
    assert boxed[int(top), int(left - pad - 3)] == 0             # nothing beyond it
    assert shadow[int(top), int(left - pad - 3)] < 175


def test_text_is_drawn_in_its_colour():
    image, b = caption_image(cap(colour="#ff8000", shadow=False, place="centre"), STYLE, PICTURE)
    a = np.asarray(image)
    solid = a[a[..., 3] == 255]
    assert len(solid) and (solid[:, :3] == (255, 128, 0)).all()


def test_maths_and_a_bigger_size_draw_wider():
    small = text_block(cap(lines=["$C_L$"]), STYLE, PICTURE).box
    big = text_block(cap(lines=["$C_L$"], size=60), STYLE, PICTURE).box
    assert big[2] - big[0] > 1.8 * (small[2] - small[0]) > 0


def test_shapes_are_in_the_caption_colour_and_share_its_shadow():
    c = cap(colour="#00ff00", place="top",
            shapes=[{"line": {"from": [50, 300], "to": [590, 300], "width": 4}},
                    {"circle": {"centre": [320, 250], "radius": 20, "width": 2,
                                "colour": "#0000ff"}}])
    image, _ = caption_image(c, STYLE, PICTURE)
    a = np.asarray(image)
    assert tuple(a[300, 320]) == (0, 255, 0, 255)
    assert tuple(a[250, 301, :3]) == (0, 0, 255)
    assert 0 < a[300 + 8, 320, 3] < 255                        # the shadow below the line


def test_a_highlight_dims_outside_its_box_beneath_the_text():
    c = cap(place="top", shadow=False,
            shapes=[{"highlight": {"from": [200, 200], "to": [400, 300], "dim": 0.5}}])
    a, _ = alpha(c)
    assert a[250, 300] == 0 and a[350, 10] == 128
    assert a.max() == 255                                       # the text over it
