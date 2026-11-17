import pytest

from flowreel.scene.errors import ConfigError
from flowreel.scene.timing import parse_time

SAVED = list(range(0, 1001, 100))   # 0, 100, ..., 1000


def test_steps_range_and_every():
    t = parse_time({"steps": [200, 700], "every": 2}, SAVED)
    assert t.steps() == [200, 400, 600] and t.n_frames == 3 and not t.frozen
    assert parse_time({"steps": [150, 350]}, SAVED).steps() == [200, 300]


def test_frozen_holds_nearest_saved_step():
    t = parse_time({"frozen": 430, "frames": 4}, SAVED)
    assert t.steps() == [400] * 4 and t.frozen
    assert parse_time({"frozen": 450}, SAVED).step(0) == 400  # tie takes the earlier


def test_keys_follow_a_linear_time_track():
    t = parse_time({"keys": [[0, 0], [10, 1000]]}, SAVED)
    assert t.n_frames == 11
    assert t.step(0) == 0 and t.step(5) == 500 and t.step(10) == 1000
    assert t.step(1) == 100                      # 100 exactly on a saved step
    t = parse_time({"keys": [[0, 0], [10, 1000]], "frames": 20}, SAVED)
    assert t.n_frames == 20 and t.step(19) == 1000   # clamped past the last key


def test_keys_eased():
    t = parse_time({"keys": [[0, 0], [10, 1000]], "ease": "in"}, SAVED)
    assert t.step(5) == 100                      # 1000 * 0.125 = 125 -> nearest saved 100


def test_step_index_bounds():
    t = parse_time({"frozen": 0, "frames": 2}, SAVED)
    with pytest.raises(IndexError):
        t.step(2)


@pytest.mark.parametrize("spec, msg", [
    ({}, "give exactly one of"),
    ({"steps": [0, 1], "frozen": 0}, "give exactly one of steps, frozen, keys, got steps, frozen"),
    ({"steps": [500, 100]}, "first <= last"),
    ({"steps": [2000, 3000]}, "no saved step in"),
    ({"steps": [0, 100], "every": 0}, "every: must be at least 1"),
    ({"steps": [0, 100], "frames": 3}, "frames: is not used with 'steps'"),
    ({"frozen": 0, "every": 2}, "every: is not used with 'frozen'"),
    ({"frozen": "x"}, "frozen: expected a number"),
    ({"keys": [[0, 0]], "ease": "bounce"}, "time: .*ease"),
    ({"stepz": [0, 1]}, "did you mean 'steps'"),
])
def test_errors(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_time(spec, SAVED)


def test_no_saved_steps():
    with pytest.raises(ConfigError, match="no saved steps"):
        parse_time({"frozen": 0}, [])
