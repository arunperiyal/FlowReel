"""Captions (film/text.py): times, places, look, shapes, freezes, text files."""
import pytest

from flowreel.film.text import Caption, Later, captions_of, load_text, parse_caption
from flowreel.scene.errors import Checker, ConfigError


def cap(**spec):
    return parse_caption({"lines": ["Hello"], **spec}, Checker("t.yml", (0,)))


def test_defaults_take_the_style_later():
    c = cap()
    assert c == Caption(lines=("Hello",))
    assert c.start == 0 and c.end is None and c.place == "bottom"
    assert c.size is None and c.box is None and c.shapes == ()


def test_times():
    assert (cap(at=[1, 4]).start, cap(at=[1, 4]).end) == (1, 4)
    assert (cap(at=2).start, cap(at=2).end) == (2, None)
    later = cap(at=[1, {"shot": "next", "at": 2.5}]).end
    assert later == Later("next", 2.5)


def test_freeze_captions_count_from_the_freeze():
    c = parse_caption({"lines": ["Frozen"]}, Checker("t.yml"), freeze=6.0)
    assert (c.start, c.end) == (0.3, 5.8)
    c = parse_caption({"lines": ["Frozen"], "at": [1]}, Checker("t.yml"), freeze=6.0)
    assert (c.start, c.end) == (1, 5.8)
    with pytest.raises(ConfigError, match="within the freeze"):
        parse_caption({"lines": ["x"], "at": [1, {"shot": "a", "at": 1}]}, Checker("t.yml"),
                      freeze=6.0)


def test_places_and_look():
    assert cap(place="top").place == "top"
    assert cap(place=[250, 575]).place == (250, 575)
    assert cap(place=["centre", 100]).place == ("centre", 100)
    c = cap(size=38, align="left", colour="#f5a142", box=True, shadow=False, fade=0.5, id="inlet")
    assert (c.size, c.align, c.colour, c.box, c.shadow, c.fade, c.id) == \
        (38, "left", "#f5a142", True, False, 0.5, "inlet")
    assert cap(lines="One line").lines == ("One line",)


def test_shapes_are_checked_when_read():
    c = cap(shapes=[{"arrow": {"from": [1, 2], "to": [3, 4], "width": 4}}])
    (s,) = c.shapes
    assert s.kind == "arrow" and s.keys == {"from": (1.0, 2.0), "to": (3.0, 4.0), "width": 4}


@pytest.mark.parametrize("spec, message", [
    ({"at": [4, 1]}, "after the start"),
    ({"at": [-1]}, "at least 0"),
    ({"at": [1, 2, 3]}, "start, end"),
    ({"place": "middle"}, "not allowed"),
    ({"place": {"model": [0, 0, 0], "view": "main"}}, "Phase 6"),
    ({"place": [1, 2, 3]}, r"\[x, y\]"),
    ({"size": 0}, "positive"),
    ({"align": "justify"}, "not allowed"),
    ({"colour": "bluish"}, "colour"),
    ({"box": "yes"}, "true or false"),
    ({"shapes": [{"arrow": {}, "line": {}}]}, "one shape"),
    ({"shapes": [{"spiral": {}}]}, "unknown key 'spiral'"),
    ({"shapes": [{"arrow": [1, 2]}]}, "mapping"),
    ({"lines": [{"Outlet": "p = 0"}]}, "must be quoted"),
    ({"size": 3, "colur": "red"}, "unknown key 'colur'"),
])
def test_errors_name_the_key(spec, message):
    with pytest.raises(ConfigError, match=message):
        cap(**spec)


def test_text_files_and_in_place_lists(tmp_path):
    (tmp_path / "domain.yml").write_text(
        "- lines: ['Inlet', 'uniform flow, $U = 1$']\n  at: [0.5, 6.5]\n  place: [250, 575]\n"
        "- {lines: ['Outlet', '$p = 0$'], at: 1}\n")
    caps = load_text(tmp_path / "domain.yml")
    assert [c.lines[0] for c in caps] == ["Inlet", "Outlet"]
    assert caps[0].lines[1] == "uniform flow, $U = 1$"
    assert captions_of(None, Checker()) == []
    assert len(captions_of([{"lines": ["a"]}, {"lines": ["b"]}], Checker())) == 2
    (tmp_path / "bad.yml").write_text("- {lines: [x], at: [3, 1]}\n")
    with pytest.raises(ConfigError, match=r"bad.yml: \[0\].at\[1\]"):
        load_text(tmp_path / "bad.yml")
