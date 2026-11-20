"""The film's timeline (film/timeline.py): lengths, freezes, caption times, counts."""
import pytest
from PIL import Image

from flowreel.film import from_dict
from flowreel.film.timeline import frame_count, layout_frames, timeline
from flowreel.scene.errors import ConfigError


def make(tmp_path, shots):
    (tmp_path / "card.yml").write_text("blocks: []\n")
    return from_dict({"fps": 24, "shots": shots}, file=str(tmp_path / "film.yml"))


SHOTS = [
    {"name": "opening", "card": "card.yml", "seconds": 7, "fade": [1.5, 1.5]},
    {"name": "domain", "frames": "f/domain", "fade": [1.5, 0],
     "text": [{"lines": ["Inlet"], "at": [0.5, 6.5]},
              {"lines": ["Across"], "at": [10, {"shot": "compare", "at": 2}]}]},
    {"name": "compare", "frames": "f/compare", "rate": {"fps": 8},
     "freezes": [{"at": 5.0, "hold": 6.0, "text": [{"lines": ["Frozen"]}]},
                 {"at": 10.0, "hold": 2.0}],
     "text": [{"lines": ["After"], "at": [12, 14]}]},
    {"name": "end", "hold_last_of": "compare", "seconds": 13, "fade": [0, 2], "fade_out_at": 0.5},
]
COUNTS = {"domain": 288, "compare": 121}          # 12 s at 24, 15.125 s at 8


def test_lengths_and_starts(tmp_path):
    t = timeline(make(tmp_path, SHOTS), COUNTS)
    assert [(s.shot.name, s.start, s.length) for s in t.shots] == [
        ("opening", 0, 7), ("domain", 7, 12), ("compare", 19, 121 / 8 + 8), ("end", 19 + 23.125, 13)]
    assert t.length == pytest.approx(7 + 12 + 23.125 + 13)


def test_freezes_follow_make_film(tmp_path):
    compare = timeline(make(tmp_path, SHOTS), COUNTS).shot("compare")
    first, second = compare.freezes
    assert (first.frame, first.start, first.hold, first.frames) == (40, 5.0, 6.0, 48)
    assert (second.frame, second.start, second.frames) == (80, 16.0, 16)   # shifted by 6
    order = compare.order
    assert order[:41] == list(range(41)) and order[41:89] == [40] * 48
    assert order[89] == 41 and order.count(80) == 17 and order[-1] == 120
    assert len(order) == 121 + 48 + 16 == compare.length * 8


def test_caption_times_across_freezes_and_cuts(tmp_path):
    t = timeline(make(tmp_path, SHOTS), COUNTS)
    found = {c.caption.lines[0]: (c.shot, c.start, c.end) for c in t.captions}
    assert found["Inlet"] == ("domain", 7.5, 13.5)
    assert found["Across"] == ("domain", 17, 21)                 # ends 2 s into compare
    assert found["Frozen"] == ("compare", 19 + 5.3, 19 + 10.8)
    assert found["After"] == ("compare", 31, 33)
    assert [c.caption.lines[0] for c in t.captions_on("compare")] == ["Across", "Frozen", "After"]


@pytest.mark.parametrize("change, message", [
    ({"text": [{"lines": ["x"], "at": [13]}]}, "at or after the end"),
    ({"text": [{"lines": ["x"], "at": [1, 13]}]}, "across the cut"),
    ({"text": [{"lines": ["x"], "at": [1, {"shot": "nope", "at": 1}]}]}, "does not have"),
    ({"text": [{"lines": ["x"], "at": [1, {"shot": "opening", "at": 1}]}]}, "does not come after"),
    ({"text": [{"lines": ["x"], "at": [1, {"shot": "end", "at": 14}]}]}, "after its 13 s"),
    ({"fade": [1, 13]}, "fades run past"),
    ({"fade": [1, 2], "fade_out_at": 11}, "fades run past"),
])
def test_errors_on_domain(tmp_path, change, message):
    shots = [dict(s) for s in SHOTS]
    shots[1] = {**shots[1], **change}
    with pytest.raises(ConfigError, match=message):
        timeline(make(tmp_path, shots), COUNTS)


def test_freeze_errors(tmp_path):
    shots = [dict(s) for s in SHOTS]
    shots[2] = {**shots[2], "freezes": [{"at": 30, "hold": 1}]}
    with pytest.raises(ConfigError, match="past the shot"):
        timeline(make(tmp_path, shots), COUNTS)
    shots[2] = {**shots[2], "freezes": [{"at": 5, "hold": 1}, {"at": 5.01, "hold": 1}]}
    with pytest.raises(ConfigError, match="two freezes"):
        timeline(make(tmp_path, shots), COUNTS)
    shots[2] = {**shots[2], "freezes": [{"at": 5, "hold": 1, "text": [{"lines": ["x"], "at": [0, 2]}]}]}
    with pytest.raises(ConfigError, match="after the freeze"):
        timeline(make(tmp_path, shots), COUNTS)


def frames(folder, n):
    folder.mkdir(parents=True)
    for i in range(n):
        Image.new("RGB", (4, 4)).save(folder / f"frame_{i:05d}.png")


def test_counts_from_frames_and_layouts(tmp_path):
    frames(tmp_path / "f" / "domain", 5)
    frames(tmp_path / "f" / "wake", 3)
    (tmp_path / "lay.yml").write_text("size: [8, 8]\ntiles: [{frames: f/wake, at: [0, 0], size: [4, 4]}]\n")
    f = from_dict({"shots": [{"name": "d", "frames": "f/domain"},
                             {"name": "l", "layout": "lay.yml", "rate": {"fps": 8}}]},
                  file=str(tmp_path / "film.yml"))
    assert frame_count(f.shots[0]) == 5 and layout_frames(tmp_path / "lay.yml") == 3
    t = timeline(f)
    assert [s.length for s in t.shots] == [5 / 24, 3 / 8]
    empty = from_dict({"shots": [{"name": "e", "frames": "nothing"}]}, file=str(tmp_path / "x.yml"))
    with pytest.raises(ConfigError, match=r"shots\[0\].*no frame_NNNNN"):
        timeline(empty)


def test_output_positions_between_frames_and_still_through_freezes(tmp_path):
    shots = [{"name": "s", "frames": "f", "rate": {"fps": 8},
              "freezes": [{"at": 0.125, "hold": 0.25}]}]
    t = timeline(make(tmp_path, shots), {"s": 3})
    s = t.shot("s")
    assert s.order == [0, 1, 1, 1, 2]
    p = s.positions(24)
    assert p == pytest.approx([0, 1 / 3, 2 / 3, 1, 1, 1, 1, 1, 1, 1, 4 / 3, 5 / 3, 2, 2, 2])
    assert len(p) == round(s.length * 24)


def test_output_positions_agree_with_compose_inside_the_shot(tmp_path):
    from flowreel.compose import output_positions
    t = timeline(make(tmp_path, [{"name": "s", "frames": "f", "rate": {"fps": 8}}]), {"s": 16})
    p = t.shot("s").positions(24)
    inside = output_positions(16, per_frame=3)
    assert p[:len(inside)] == pytest.approx(inside) and p[len(inside):] == [15, 15]
    full = timeline(make(tmp_path, [{"name": "s", "frames": "f"}]), {"s": 5}).shot("s")
    assert full.positions(24) == [0, 1, 2, 3, 4]
    with pytest.raises(ValueError, match="no frames"):
        timeline(make(tmp_path, SHOTS), COUNTS).shot("opening").positions(24)
