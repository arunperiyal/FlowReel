"""The film file (film/schema.py): shots, rates, freezes, style, audio, watermark."""
from pathlib import Path

import pytest

from flowreel.film import from_dict, load
from flowreel.scene.errors import ConfigError


def film(tmp_path, shots=None, **keys):
    (tmp_path / "cards").mkdir(exist_ok=True)
    (tmp_path / "cards" / "opening.yml").write_text("blocks: []\n")
    (tmp_path / "compare.yml").write_text("tiles: []\n")
    (tmp_path / "text").mkdir(exist_ok=True)
    (tmp_path / "text" / "domain.yml").write_text("- {lines: [Inlet], at: [1, 4]}\n")
    shots = shots or [
        {"name": "opening", "card": "cards/opening.yml", "seconds": 7, "fade": [1.5, 1.5]},
        {"name": "domain", "frames": "frames/domain", "fade": [1.5, 0], "text": "text/domain.yml"},
        {"name": "compare", "layout": "compare.yml", "rate": {"fps": 8},
         "freezes": [{"at": 5.0, "hold": 6.0, "text": [{"lines": ["Frozen"]}]}]},
        {"name": "end", "hold_last_of": "compare", "seconds": 13, "fade": [0, 2],
         "fade_out_at": 0.5}]
    return from_dict({"shots": shots, **keys}, file=str(tmp_path / "film.yml"))


def test_shots_of_every_kind(tmp_path):
    f = film(tmp_path)
    assert f.fps == 24 and f.size == (1920, 1080) and f.output == tmp_path / "film.mp4"
    opening, domain, compare, end = f.shots
    assert (opening.kind, opening.source, opening.seconds) == \
        ("card", tmp_path / "cards" / "opening.yml", 7)
    assert domain.kind == "frames" and domain.source == tmp_path / "frames" / "domain"
    assert domain.rate.fps == 24 and [c.lines for c in domain.text] == [("Inlet",)]
    assert compare.kind == "layout" and compare.rate.fps == 8
    assert compare.rate.to_output == "interpolate"
    assert compare.freezes[0].at == 5 and compare.freezes[0].hold == 6
    (frozen,) = compare.freezes[0].text
    assert frozen.lines == ("Frozen",) and (frozen.start, frozen.end) == (0.3, 5.8)
    assert end.kind == "hold" and end.source == "compare" and end.overlays
    assert end.fade == (0, 2) and end.fade_out_at == 0.5
    assert f.shot("domain") is domain
    with pytest.raises(KeyError, match="no shot 'x'"):
        f.shot("x")


def test_style_audio_and_watermark(tmp_path):
    f = film(tmp_path, fps=48, size=[1280, 720],
             style={"colours": {"text": "#ffffff"}, "caption": {"size": 40, "box": True}},
             audio={"file": "music.mp3", "volume": 0.8, "fade": [1.5, 4], "licence": "CC0"},
             watermark={"text": "A. P.", "corner": "upper_left", "shots": ["domain"]})
    assert f.style.text == "#ffffff" and f.style.muted == "#96a5b2"
    assert f.style.caption.size == 40 and f.style.caption.box and f.style.caption.fade == 0.8
    (a,) = f.audio
    assert a.file == tmp_path / "music.mp3" and a.fade == (1.5, 4) and a.licence == "CC0"
    assert f.watermark.text == "A. P." and f.watermark.shots == ("domain",)
    assert f.watermark.corner == "upper_left" and not f.watermark.cards
    two = film(tmp_path, audio=[{"file": "a.mp3", "start": 10, "fade": 2}, {"file": "b.wav"}])
    assert [t.start for t in two.audio] == [10, 0] and two.audio[0].fade == (2, 2)


@pytest.mark.parametrize("shot, message", [
    ({"name": "a"}, "give one of"),
    ({"name": "a", "frames": "f", "card": "cards/opening.yml"}, "give one of"),
    ({"name": "a", "frames": "f", "seconds": 3}, "seconds.*cards and holds"),
    ({"name": "a", "card": "cards/opening.yml"}, "missing key 'seconds'"),
    ({"name": "a", "card": "cards/opening.yml", "seconds": 2, "rate": {"fps": 8}}, "still"),
    ({"name": "a", "card": "nope.yml", "seconds": 2}, "no card file"),
    ({"name": "a", "frames": "f", "rate": {"fps": 7}}, "whole number"),
    ({"name": "a", "frames": "f", "rate": {"fps": 48}}, "at most the film's 24"),
    ({"name": "a", "frames": "f", "rate": {"to_output": "smear"}}, "to_output"),
    ({"name": "a", "frames": "f", "freezes": [{"at": 3, "hold": 1}, {"at": 1, "hold": 1}]},
     "in order"),
    ({"name": "a", "frames": "f", "freezes": [{"at": 3, "hold": 0}]}, "positive"),
    ({"name": "a", "frames": "f", "fade_out_at": 2}, "fade out"),
    ({"name": "a", "frames": "f", "overlays": False}, "hold_last_of"),
    ({"name": "a", "frames": "f", "text": "missing.yml"}, "no text file"),
    ({"name": "a", "frames": "f", "colour": "red"}, "unknown key"),
])
def test_shot_errors(tmp_path, shot, message):
    with pytest.raises(ConfigError, match=message):
        film(tmp_path, shots=[shot])


def test_film_errors(tmp_path):
    with pytest.raises(ConfigError, match="named twice"):
        film(tmp_path, shots=[{"name": "a", "frames": "f"}, {"name": "a", "frames": "g"}])
    with pytest.raises(ConfigError, match="no shot 'b'"):
        film(tmp_path, shots=[{"name": "a", "hold_last_of": "b", "seconds": 2}])
    with pytest.raises(ConfigError, match="is a card"):
        film(tmp_path, shots=[{"name": "c", "card": "cards/opening.yml", "seconds": 2},
                              {"name": "a", "hold_last_of": "c", "seconds": 2}])
    with pytest.raises(ConfigError, match=r"watermark.*give one of"):
        film(tmp_path, watermark={"corner": "upper_left"})
    with pytest.raises(ConfigError, match=r"watermark.shots\[0\].*no shot 'x'"):
        film(tmp_path, watermark={"text": "w", "shots": ["x"]})
    with pytest.raises(ConfigError, match="opacity"):
        film(tmp_path, watermark={"text": "w", "opacity": 2})
    with pytest.raises(ConfigError, match="missing key 'shots'"):
        from_dict({}, file="f.yml")


def test_load_names_the_file(tmp_path):
    (tmp_path / "film.yml").write_text("shots: [{name: a, frames: f}]\n")
    assert load(tmp_path / "film.yml").shots[0].name == "a"
    (tmp_path / "bad.yml").write_text("shots: [\n")
    with pytest.raises(ConfigError, match=r"bad.yml: line"):
        load(tmp_path / "bad.yml")
