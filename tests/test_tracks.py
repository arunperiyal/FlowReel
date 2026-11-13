"""Exact-value tests for tracks, easings, value types and the time track."""
import pytest

from flowreel import tracks
from flowreel.tracks import TimeTrack, Track, blend, ease, nearest_step, parse


# --- parsing -----------------------------------------------------------------------

def test_fixed_value_is_a_single_key():
    t = parse(1.0, name="opacity")
    assert t.frames == (0.0,) and t.values == (1.0,)
    assert t.kind == "number" and t.fixed and t.name == "opacity"
    assert t.at(-100) == 1.0 and t.at(0) == 1.0 and t.at(1e6) == 1.0


def test_from_to_frames():
    t = parse({"from": 0.02, "to": 6.0, "frames": [48, 72]})
    assert t.frames == (48, 72) and t.values == (0.02, 6.0)
    assert t.ease == "smooth" and not t.fixed


def test_keys_and_ease():
    t = parse({"keys": [[0, -0.1], [120, -1.0]], "ease": "out"}, name="level")
    assert t.frames == (0, 120) and t.values == (-0.1, -1.0) and t.ease == "out"


def test_keys_with_equal_values_are_fixed():
    assert parse({"keys": [[0, 2], [10, 2]]}).fixed


def test_parse_returns_a_track_unchanged():
    t = parse(3)
    assert parse(t) is t and isinstance(t, Track)


@pytest.mark.parametrize("spec, message", [
    ({"keys": [[0, 0], [72, 1], [58, 0]]}, "grey: frames in 'keys' must increase, but 58 follows 72"),
    ({"keys": [[0, 0], [58, 0], [58, 1]]}, "grey: frame 58 appears twice in 'keys'"),
    ({"from": 0, "to": 1, "frames": [72, 48]}, "grey: frames in 'frames' must increase"),
    ({"from": 0, "to": 1, "frames": [48, 48]}, "grey: frame 48 appears twice in 'frames'"),
    ({"from": 0, "to": 1, "frames": [48]}, "grey: 'frames' must be [start, end]"),
    ({"from": 0, "frames": [0, 1]}, "grey: missing key 'to'"),
    ({"keys": [[0, 0], [1, 1]], "ease": "bounce"}, "grey: unknown ease 'bounce'"),
    ({"keys": [[0, 0], [1, 1]], "easing": "out"}, "grey: unknown key 'easing'"),
    ({"keys": [[0, 0]], "from": 0}, "grey: 'keys' cannot be combined with 'from'"),
    ({"keys": []}, "grey: 'keys' must be a list of [frame, value] pairs"),
    ({"keys": [[0, 0, 1]]}, "grey: each entry of 'keys' must be [frame, value]"),
    ({"keys": [["a", 0]]}, "grey: frame 'a' in 'keys' is not a number"),
    ({"ease": "out"}, "grey: needs 'keys' or from/to/frames"),
    ({"keys": [[0, 0], [1, "a"]]}, "grey: mixed value types (number and choice)"),
    ({"keys": [[0, 1], [1, True]]}, "grey: mixed value types (number and boolean)"),
    ({"keys": [[0, [1, 2]], [1, 3]]}, "grey: mixed value types (vector and number)"),
    ({"keys": [[0, [1, 2]], [1, [1, 2, 3]]]}, "grey: mixed value types (vectors of 2 and 3"),
    (None, "grey: cannot use None as a track value"),
])
def test_malformed_specs_name_the_bad_key(spec, message):
    with pytest.raises(ValueError) as err:
        parse(spec, name="grey")
    assert str(err.value).startswith(message)


def test_unknown_kind():
    with pytest.raises(ValueError, match="unknown kind 'angle'"):
        parse(1, kind="angle")


# --- easings -----------------------------------------------------------------------

@pytest.mark.parametrize("name, quarter, half, three_quarters", [
    ("linear", 0.25, 0.5, 0.75),
    ("smooth", 0.15625, 0.5, 0.84375),
    ("in", 0.015625, 0.125, 0.421875),
    ("out", 0.578125, 0.875, 0.984375),
    ("in_out", 0.0625, 0.5, 0.9375),
    ("hold", 0.0, 0.0, 0.0),
])
def test_easing_values(name, quarter, half, three_quarters):
    assert ease(name, 0) == 0 and ease(name, 1) == 1
    assert ease(name, 0.25) == quarter
    assert ease(name, 0.5) == half
    assert ease(name, 0.75) == three_quarters


def test_easings_clamp_and_reject_unknown_names():
    for name in tracks.EASE_NAMES:
        assert ease(name, -2) == 0 and ease(name, 3) == 1
    with pytest.raises(ValueError, match="unknown ease 'bounce'"):
        ease("bounce", 0.5)


def test_smooth_matches_the_prototype_ramp():
    # prototype/afms/render_frames.py: ramp(z, start, end) = t * t * (3 - 2 * t)
    def ramp(z, start, end):
        t = min(max((z - start) / (end - start), 0), 1)
        return t * t * (3 - 2 * t)

    t = parse({"from": 0.0, "to": 1.0, "frames": [48, 72]})
    for frame in range(40, 80):
        assert t.at(frame) == ramp(frame, 48, 72)


def test_default_ease_is_smooth():
    assert tracks.DEFAULT_EASE == "smooth"
    t = parse({"from": 0.0, "to": 8.0, "frames": [0, 4]})
    assert [t.at(f) for f in range(5)] == [0.0, 1.25, 4.0, 6.75, 8.0]


@pytest.mark.parametrize("name, expected", [
    ("linear", [0.0, 2.0, 4.0, 6.0, 8.0]),
    ("in", [0.0, 0.125, 1.0, 3.375, 8.0]),
    ("out", [0.0, 4.625, 7.0, 7.875, 8.0]),
    ("in_out", [0.0, 0.5, 4.0, 7.5, 8.0]),
    ("hold", [0.0, 0.0, 0.0, 0.0, 8.0]),
])
def test_eased_number_track(name, expected):
    t = parse({"from": 0, "to": 8, "frames": [0, 4], "ease": name})
    assert [t.at(f) for f in range(5)] == expected


# --- value types -------------------------------------------------------------------

def test_number_track_with_several_keys():
    t = parse({"keys": [[0, 0], [58, 0], [72, 1]], "ease": "linear"}, name="grey")
    assert t.at(30) == 0.0 and t.at(58) == 0.0 and t.at(65) == 0.5 and t.at(72) == 1.0
    assert isinstance(t.at(0), float)


def test_fractional_frames():
    t = parse({"from": 0, "to": 4, "frames": [0, 2], "ease": "linear"})
    assert t.at(0.5) == 1.0 and t(1.25) == 2.5


def test_vector_track():
    t = parse({"from": [0, 0, 0], "to": [2, 4, -8], "frames": [0, 4], "ease": "linear"})
    assert t.kind == "vector"
    assert t.at(1) == (0.5, 1.0, -2.0) and t.at(4) == (2.0, 4.0, -8.0)
    assert parse([1, 2, 3]).at(7) == (1.0, 2.0, 3.0)


def test_colour_parsing():
    assert tracks.parse_colour("#ffffff") == (1.0, 1.0, 1.0)
    assert tracks.parse_colour("#000") == (0.0, 0.0, 0.0)
    assert tracks.parse_colour("#f80") == tracks.parse_colour("#FF8800") == (1.0, 136 / 255, 0.0)
    assert tracks.parse_colour([0.25, 0.5, 1]) == (0.25, 0.5, 1.0)
    for bad in ("red", "#ffff", [255, 0, 0], [0.1, 0.2], 3):
        with pytest.raises(ValueError, match="expected a colour"):
            tracks.parse_colour(bad)


def test_colour_kind_is_inferred_from_hex_and_forced_for_lists():
    assert parse("#96a5b2").kind == "colour"
    assert parse([1, 1, 1]).kind == "vector"
    assert parse([1, 1, 1], kind="colour").kind == "colour"
    t = parse({"keys": [[0, "#000000"], [10, [1, 1, 1]]]}, kind="colour")
    assert t.values == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    with pytest.raises(ValueError, match="text: expected a colour"):
        parse("red", kind="colour", name="text")


def test_colours_blend_in_linear_rgb():
    t = parse({"from": "#000000", "to": "#ffffff", "frames": [0, 2], "ease": "linear"})
    # Linear-light 0.5 encoded as sRGB, not the sRGB midpoint 0.5.
    mid = 1.055 * 0.5 ** (1 / 2.4) - 0.055
    assert t.at(1) == (mid, mid, mid)
    assert mid == pytest.approx(0.7353569830524495, abs=1e-15)
    assert t.at(0) == (0.0, 0.0, 0.0) and t.at(2) == (1.0, 1.0, 1.0)


def test_colour_blend_per_channel():
    red_to_blue = blend("colour", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.5)
    mid = tracks.linear_to_srgb(0.5)
    assert red_to_blue == (mid, 0.0, mid)


def test_srgb_transfer_functions():
    assert tracks.srgb_to_linear(0.0) == 0.0 and tracks.srgb_to_linear(1.0) == 1.0
    assert tracks.linear_to_srgb(0.0) == 0.0
    assert tracks.linear_to_srgb(1.0) == pytest.approx(1.0, abs=1e-15)
    assert tracks.srgb_to_linear(0.04045) == 0.04045 / 12.92
    assert tracks.srgb_to_linear(0.5) == pytest.approx(0.21404114048223255, abs=1e-15)
    for c in (0.001, 0.02, 0.2, 0.5, 0.9):
        assert tracks.linear_to_srgb(tracks.srgb_to_linear(c)) == pytest.approx(c, abs=1e-12)


def test_boolean_track_steps():
    t = parse({"keys": [[0, False], [10, True], [20, False]]}, name="visible")
    assert t.kind == "boolean" and t.ease == "hold"
    assert [t.at(f) for f in (-5, 0, 9.99, 10, 15, 20, 99)] == \
        [False, False, False, True, True, False, False]
    assert parse(True).at(3) is True


def test_choice_track_steps():
    t = parse({"keys": [[0, "viridis"], [50, "magma"]], "ease": "hold"}, name="colormap")
    assert t.kind == "choice"
    assert t.at(49) == "viridis" and t.at(50) == "magma" and t.at(51) == "magma"
    assert parse("#fff", kind="choice").values == ("#fff",)


def test_stepped_kinds_reject_other_easings():
    with pytest.raises(ValueError, match="visible: ease 'linear' cannot be used with boolean"):
        parse({"keys": [[0, False], [10, True]], "ease": "linear"}, name="visible")
    with pytest.raises(ValueError, match="cannot be used with choice"):
        parse({"from": "a", "to": "b", "frames": [0, 1], "ease": "smooth"})


@pytest.mark.parametrize("spec, kind, message", [
    ("a", "number", "x: expected a number, got 'a'"),
    (True, "number", "x: expected a number, got True"),
    (3, "vector", "x: expected a list of numbers, got 3"),
    (1, "boolean", "x: expected true or false, got 1"),
    (1, "choice", "x: expected a name (text), got 1"),
    (float("nan"), None, "x: cannot use nan as a track value"),
])
def test_values_must_match_the_kind(spec, kind, message):
    with pytest.raises(ValueError) as err:
        parse(spec, kind=kind, name="x")
    assert str(err.value) == message


def test_blend_end_points_are_exact():
    assert blend("number", 0.1, 0.7, 0) == 0.1 and blend("number", 0.1, 0.7, 1) == 0.7
    assert blend("choice", "a", "b", 0.99) == "a" and blend("choice", "a", "b", 1) == "b"
    with pytest.raises(ValueError, match="unknown kind"):
        blend("angle", 0, 1, 0.5)


# --- clamping and the time track ---------------------------------------------------

def test_clamping():
    t = parse({"keys": [[10, 2.0], [20, 4.0], [30, -1.0]]})
    assert t.at(-1000) == 2.0 and t.at(9.999) == 2.0 and t.at(10) == 2.0
    assert t.at(30) == -1.0 and t.at(30.001) == -1.0 and t.at(1e9) == -1.0
    assert t.at(20) == 4.0


def test_time_track_is_linear_by_default():
    time = TimeTrack({"keys": [[0, 5000], [120, 5300]]})
    assert time.track.ease == "linear"
    assert time.at(0) == 5000.0 and time.at(60) == 5150.0 and time.at(120) == 5300.0
    assert time.at(-5) == 5000.0 and time.at(500) == 5300.0
    assert TimeTrack({"keys": [[0, 0], [4, 8]], "ease": "in"}).at(2) == 1.0


def test_time_track_takes_the_nearer_saved_step():
    time = TimeTrack({"keys": [[0, 5000], [120, 5300]]})
    saved = list(range(5000, 5301, 50))
    assert time.step(0, saved) == 5000
    assert time.step(9, saved) == 5000       # asks for 5022.5
    assert time.step(11, saved) == 5050      # asks for 5027.5
    assert time.step(60, saved) == 5150
    assert time.step(120, saved) == 5300 and time.step(999, saved) == 5300


def test_time_track_tie_takes_the_earlier_step():
    time = TimeTrack({"keys": [[0, 5000], [120, 5300]]})
    assert time.at(10) == 5025.0
    assert time.step(10, [5000, 5050]) == 5000
    assert nearest_step(15, [10, 20]) == 10 and nearest_step(15.0001, [10, 20]) == 20


def test_nearest_step_edges():
    assert nearest_step(3, [10, 20, 30]) == 10 and nearest_step(99, [10, 20, 30]) == 30
    assert nearest_step(26, [30, 10, 20]) == 30          # order does not matter
    assert nearest_step(7, [7]) == 7
    with pytest.raises(ValueError, match="no saved steps"):
        nearest_step(1, [])


def test_fixed_time_freezes_the_flow():
    time = TimeTrack(5120)
    assert time.step(0, [5000, 5100, 5200]) == 5100 and time.step(400, [5000, 5100, 5200]) == 5100


def test_time_track_needs_numbers():
    with pytest.raises(ValueError, match="time: expected a number"):
        TimeTrack({"keys": [[0, "a"], [1, "b"]]})
