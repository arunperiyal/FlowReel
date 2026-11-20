"""2D shapes (film/shapes.py): keys checked when read, pixels where they are drawn."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from flowreel.film import shapes
from flowreel.film.shapes import Shape, parse_shape
from flowreel.scene.errors import Checker, ConfigError

SIZE = (200, 100)


def shape(**spec):
    return parse_shape(spec, Checker("t.yml", ("shapes", 0)))


def drawn(s: Shape, colour="#ff0000"):
    """The shape drawn on a transparent picture; its alpha as an array."""
    image = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    (s,) = shapes.parse_all([s], colour)
    shapes.draw(ImageDraw.Draw(image), s)
    return np.asarray(image)


def test_points_and_numbers_are_read():
    s = shape(box={"from": [10, 20], "to": [30, 40], "radius": 3, "fill": "black"})
    assert s.kind == "box"
    assert s["from"] == (10.0, 20.0) and s["to"] == (30.0, 40.0) and s["radius"] == 3
    assert s["fill"] == "black"


def test_a_shape_takes_the_caption_colour_unless_it_names_one():
    (a, b, h) = shapes.parse_all([shape(line={"from": [0, 0], "to": [1, 1]}),
                                  shape(line={"from": [0, 0], "to": [1, 1], "colour": "#00ff00"}),
                                  shape(highlight={"from": [0, 0], "to": [1, 1]})], "#f5a142")
    assert a["colour"] == "#f5a142" and b["colour"] == "#00ff00"
    assert h.get("colour") is None


@pytest.mark.parametrize("spec, message", [
    ({"arrow": {"from": [0, 0]}}, "missing key 'to'"),
    ({"arrow": {"from": [0, 0], "to": [0, 0]}}, "must differ"),
    ({"arrow": {"from": [0, 0], "to": [1, 1], "widht": 3}}, "unknown key 'widht'"),
    ({"arrow": {"from": [0, 0], "to": [1, 1], "width": 0}}, "positive"),
    ({"circle": {"centre": [0, 0], "radius": -1}}, "positive"),
    ({"line": {"from": [0, 0, 0], "to": [1, 1]}}, "2"),
    ({"line": {"from": {"model": [0, 0, 0], "view": "main"}, "to": [1, 1]}}, "Phase 6"),
    ({"highlight": {"from": [0, 0], "to": [1, 1], "dim": 2}}, "0 to 1"),
    ({"box": {"from": [0, 0], "to": [1, 1], "colour": "bluish"}}, "colour"),
    ({"spiral": {}}, "unknown key 'spiral'"),
])
def test_errors_name_the_key(spec, message):
    with pytest.raises(ConfigError, match=message) as e:
        parse_shape(spec, Checker("t.yml", ("shapes", 0)))
    assert "t.yml" in str(e.value) and "shapes" in str(e.value)


def test_an_arrow_ends_in_a_head_at_its_point():
    a = drawn(shape(arrow={"from": [20, 50], "to": [180, 50], "width": 4}))
    assert tuple(a[50, 100]) == (255, 0, 0, 255)          # the shaft
    assert a[50, 179, 3] == 255 and a[50, 182, 3] == 0    # the tip, at x = 180
    head = 4.5 * 4                                        # long; half as wide
    assert a[50 - 4, 172, 3] == 255 and a[50 - 4, 100, 3] == 0
    assert a[int(50 - head / 2) - 2, 162, 3] == 0


def test_a_box_and_a_circle_are_outlined_unless_filled():
    a = drawn(shape(box={"from": [150, 80], "to": [50, 20], "width": 2}))
    assert a[20, 100, 3] == 255 and a[50, 50, 3] == 255 and a[50, 100, 3] == 0
    a = drawn(shape(box={"from": [50, 20], "to": [150, 80], "fill": "blue"}))
    assert tuple(a[50, 100]) == (0, 0, 255, 255)
    a = drawn(shape(circle={"centre": [100, 50], "radius": 30, "width": 2}))
    assert a[50, 71, 3] == 255 and a[50, 100, 3] == 0 and a[50, 65, 3] == 0


def test_an_ellipse_has_its_two_radii():
    a = drawn(shape(ellipse={"centre": [100, 50], "radii": [60, 20], "width": 2}))
    assert a[50, 41, 3] == 255 and a[50, 159, 3] == 255     # 60 across
    assert a[31, 100, 3] == 255 and a[69, 100, 3] == 255    # 20 up and down
    assert a[50, 35, 3] == 0


def test_a_bracket_turns_its_tips_to_the_left_of_its_direction():
    """Drawn left to right, its left is up: the tips rise from y = 70 to y = 50."""
    a = drawn(shape(bracket={"from": [40, 70], "to": [160, 70], "depth": 20, "width": 2}))
    assert a[70, 100, 3] == 255
    assert a[55, 40, 3] == 255 and a[55, 160, 3] == 255 and a[85, 40, 3] == 0
    b = drawn(shape(bracket={"from": [160, 70], "to": [40, 70], "depth": 20, "width": 2}))
    assert b[85, 40, 3] == 255 and b[55, 40, 3] == 0


def test_a_dimension_is_moved_by_its_offset_with_lines_back_to_its_ends():
    s = shape(dimension={"from": [40, 80], "to": [160, 80], "offset": 30, "value": "$2D$"})
    a = drawn(s)
    assert a[50, 100, 3] == 255 and a[80, 100, 3] == 0       # the line, 30 px up
    assert a[65, 40, 3] == 255 and a[65, 160, 3] == 255      # lines back to the ends
    assert a[50, 41, 3] == 255 and a[50, 159, 3] == 255      # heads at the ends
    x, y = shapes.label_place(s, 20)
    assert (x, y) == pytest.approx((100, 80 - 30 - 16))      # above the line


def test_a_highlight_darkens_only_outside_its_box():
    s = shape(highlight={"from": [50, 20], "to": [150, 80], "dim": 0.5})
    a = np.asarray(shapes.highlight_layer(s, SIZE))
    assert a[50, 100, 3] == 0 and a[5, 5, 3] == 128 and a[90, 190, 3] == 128
    assert drawn(s)[..., 3].max() == 0                      # not drawn with the others
