import numpy as np
import pytest

from flowreel.box import Box


def test_bounds_round_trip():
    b = Box.from_bounds((0, 2, -1, 1, 5, 9))
    assert b.lo == (0, -1, 5) and b.hi == (2, 1, 9)
    assert b.to_bounds() == (0, 2, -1, 1, 5, 9)


def test_size_and_center():
    b = Box((0, 0, 0), (2, 4, 6))
    assert b.size == (2, 4, 6) and b.center == (1, 2, 3)


def test_contains_includes_edges():
    b = Box((0, 0, 0), (1, 1, 1))
    pts = [[0.5, 0.5, 0.5], [1, 1, 1], [1.01, 0.5, 0.5]]
    assert b.contains(pts).tolist() == [True, True, False]


def test_intersection():
    a, b = Box((0, 0, 0), (2, 2, 2)), Box((1, 1, 1), (3, 3, 3))
    assert a.intersection(b) == Box((1, 1, 1), (2, 2, 2))
    assert a.intersection(Box((5, 5, 5), (6, 6, 6))) is None
    assert a.intersects(Box((2, 2, 2), (3, 3, 3)))  # touching counts


def test_expanded():
    assert Box((0, 0, 0), (1, 1, 1)).expanded(0.5) == Box((-0.5,) * 3, (1.5,) * 3)


def test_invalid():
    with pytest.raises(ValueError):
        Box((1, 0, 0), (0, 1, 1))
    with pytest.raises(ValueError):
        Box.from_bounds((0, 1, 2))
