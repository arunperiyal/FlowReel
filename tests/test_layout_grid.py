"""grid: [rows, cols] places tiles row by row, with a gap between cells."""
import pytest

from flowreel.compose import from_dict
from flowreel.compose.layout import grid_cells
from flowreel.scene.errors import ConfigError


def test_cells_of_a_two_by_two_grid():
    assert grid_cells((100, 50), (2, 2), gap=10) == [
        ((0, 0), (45, 20)), ((55, 0), (45, 20)),
        ((0, 30), (45, 20)), ((55, 30), (45, 20))]


def test_cells_round_to_pixels_and_end_at_the_edge():
    cells = grid_cells((100, 10), (1, 3), gap=0)
    assert [c[0][0] for c in cells] == [0, 33, 67]
    (x, _), (w, _) = cells[-1]
    assert x + w == 100
    assert {c[1][0] for c in cells} <= {33, 34}


def test_tiles_fill_the_grid_in_order():
    lay = from_dict({"size": [200, 100], "grid": [1, 2], "gap": 4,
                     "tiles": [{"frames": "a"}, {"frames": "b", "label": "b"}]})
    assert [(t.at, t.size) for t in lay.tiles] == [((0, 0), (98, 100)), ((102, 0), (98, 100))]
    assert lay.tiles[1].label.text == "b"


def test_a_grid_may_have_empty_cells():
    lay = from_dict({"size": [90, 90], "grid": [3, 3], "tiles": [{"frames": "a"}]})
    assert lay.tiles[0].size == (30, 30)


@pytest.mark.parametrize("data, msg", [
    ({"grid": [1, 1], "tiles": [{"frames": "a"}, {"frames": "b"}]}, r"tiles: 2 tiles do not fit a grid of 1 x 1"),
    ({"grid": [1, 2], "tiles": [{"frames": "a", "at": [0, 0]}]}, r"tiles\[0\]\.at: is set by 'grid'"),
    ({"grid": [1, 0], "tiles": [{"frames": "a"}]}, r"grid\[1\]: must be at least 1"),
    ({"size": [20, 20], "grid": [1, 3], "gap": 10, "tiles": [{"frames": "a"}]}, r"gap: a gap of 10 leaves no room"),
    ({"gap": 4, "tiles": [{"frames": "a", "at": [0, 0], "size": [1, 1]}]}, r"gap: is used only with 'grid'"),
])
def test_errors(data, msg):
    with pytest.raises(ConfigError, match=msg):
        from_dict(data)
