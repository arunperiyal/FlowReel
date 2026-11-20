"""Card files (film/cards.py): blocks checked when read, and placed down the card."""
import pytest
from PIL import Image

from flowreel.film.cards import card_from_dict, height, layout, load_card
from flowreel.scene.errors import ConfigError


@pytest.fixture
def logo(tmp_path):
    """A 100 x 50 logo beside the card file."""
    path = tmp_path / "logo.png"
    Image.new("RGBA", (100, 50), (255, 255, 255, 255)).save(path)
    return path


def card(tmp_path, *blocks, **top):
    return card_from_dict({"blocks": list(blocks), **top}, file=str(tmp_path / "card.yml"))


def test_defaults_are_the_afms_opening_cards(tmp_path):
    c = card(tmp_path, {"title": "A title"}, {"divider": True}, {"heading": "BY", "names": ["A"]},
             {"text": ["Small print"]})
    title, divider, names, text = c.blocks
    assert c.size == (1920, 1080) and c.background == "black"
    assert title.keys == {"title": ("A title",), "size": 60, "weight": "regular", "spacing": 78}
    assert divider.keys == {"divider": 320, "thickness": 2}
    assert (names["size"], names["spacing"], names["weight"]) == (42, 58, "light")
    assert (names["heading_size"], names["heading_gap"], names["heading"]) == (28, 44, "BY")
    assert text["size"] == 24 and text["spacing"] == 31
    assert all(b.get("colour") is None for b in c.blocks)    # the film's colours, at drawing


def test_blocks_go_down_the_card_by_y_or_gap(tmp_path, logo):
    """The AFMS opening card's layout: logo, title, divider and two groups of names."""
    c = card(tmp_path, {"image": "logo.png", "height": 190, "y": 110},
             {"title": ["One", "Two"], "spacing": 82, "gap": 70},
             {"divider": 320, "gap": 38},
             {"heading": "CREATED BY", "names": ["A"], "gap": 46},
             {"heading": "CO-AUTHORED BY", "names": ["B", "C"], "gap": 26})
    assert layout(c) == [(110, 300), (370, 534), (572, 574), (620, 722), (748, 908)]


def test_an_image_is_as_tall_as_given_or_its_own(tmp_path, logo):
    own, wide = card(tmp_path, {"image": "logo.png"}, {"image": "logo.png", "width": 300}).blocks
    assert height(own) == 50 and height(wide) == 150


def test_names_without_a_heading_and_a_negative_gap(tmp_path):
    c = card(tmp_path, {"names": ["A", "B"], "y": 100}, {"text": "x", "gap": -16})
    assert layout(c) == [(100, 216), (200, 231)]


def test_size_background_and_colours(tmp_path, logo):
    c = card(tmp_path, {"title": "T", "colour": "orange"}, size=[1280, 720],
             background="#102030", background_image="logo.png")
    assert c.size == (1280, 720) and c.background == "#102030"
    assert c.background_image == logo and c.blocks[0]["colour"] == "orange"


def test_a_card_file_is_read(tmp_path):
    (tmp_path / "card.yml").write_text("blocks:\n  - {title: 'Hello', size: 50}\n")
    c = load_card(tmp_path / "card.yml")
    assert c.blocks[0]["title"] == ("Hello",) and c.file.endswith("card.yml")


@pytest.mark.parametrize("blocks, top, message", [
    ([], {}, "at least 1"),
    ([{"title": "T", "text": "x"}], {}, "give one of"),
    ([{"size": 3}], {}, "give one of"),
    ([{"heading": "BY", "title": "T"}], {}, "heading of 'names'"),
    ([{"title": "T", "y": 1, "gap": 2}], {}, "not both"),
    ([{"title": "T", "colour": "bluish"}], {}, "colour"),
    ([{"title": "T", "weight": "heavy"}], {}, "not allowed"),
    ([{"title": "T", "size": 0}], {}, "positive"),
    ([{"title": "T", "widht": 3}], {}, "unknown key 'widht'"),
    ([{"title": [{"Outlet": "p"}]}], {}, "quote"),
    ([{"image": "nowhere.png"}], {}, "no image file"),
    ([{"title": "T"}], {"size": [100.5, 50]}, "whole numbers"),
    ([{"title": "T"}], {"colour": "red"}, "unknown key 'colour'"),
    ([{"title": "T"}], {"background_image": "none.png"}, "no image file"),
])
def test_errors_name_the_file_and_key(tmp_path, blocks, top, message):
    with pytest.raises(ConfigError, match=message) as e:
        card(tmp_path, *blocks, **top)
    assert "card.yml" in str(e.value)
