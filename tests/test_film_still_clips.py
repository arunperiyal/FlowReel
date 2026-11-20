"""Base clips of cards and holds: a still for the shot's seconds, keyed by its pixels."""
import numpy as np
import pytest
import yaml

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.clips import Clips

from film_project import colour, decode, film_file, frames, mean_colour, need_ffmpeg
from test_film_layout_clip import board


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def write_card(folder, title="Hello"):
    (folder / "card.yml").write_text(yaml.safe_dump(
        {"size": [160, 90], "background": "#203040",
         "blocks": [{"title": title, "size": 20, "y": 30, "colour": "#ffffff"}]}))


def test_a_card_is_drawn_and_held_for_its_seconds(tmp_path):
    write_card(tmp_path)
    c = Clips(film.load(film_file(tmp_path, [{"name": "o", "card": "card.yml", "seconds": 1.5}])))
    clip = c.base("o")
    assert clip.frames == 36 and ff.frame_count(clip.path) == 36
    p = decode(clip.path).astype(int)
    assert np.abs(p[0, 5, 5] - (0x20, 0x30, 0x40)).max() < 6     # the background
    assert p[0, 30:60].max() > 200                              # the title
    assert np.abs(p[35] - p[0]).max() < 6


def test_a_card_is_rebuilt_only_when_its_picture_changes(tmp_path):
    write_card(tmp_path)
    shots = [{"name": "o", "card": "card.yml", "seconds": 1}]
    first = Clips(film.load(film_file(tmp_path, shots))).base("o")
    (tmp_path / "card.yml").write_text((tmp_path / "card.yml").read_text() + "\n# a comment\n")
    assert not Clips(film.load(tmp_path / "film.yml")).base("o").built
    write_card(tmp_path, title="Goodbye")
    assert Clips(film.load(tmp_path / "film.yml")).base("o").built


def test_a_hold_shows_the_last_frame_of_a_frames_shot(tmp_path):
    frames(tmp_path / "f", 5)
    c = Clips(film.load(film_file(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8}},
                                             {"name": "end", "hold_last_of": "a", "seconds": 1}])))
    p = decode(c.base("end").path)
    assert p.shape[0] == 24 and np.abs(mean_colour(p[12]) - colour(4)).max() < 6


def test_a_hold_of_a_layout_with_or_without_its_live_panels(tmp_path):
    board(tmp_path)
    shots = [{"name": "c", "layout": "board.yml", "rate": {"fps": 8}},
             {"name": "end", "hold_last_of": "c", "seconds": 0.5},
             {"name": "bare", "hold_last_of": "c", "seconds": 0.5, "overlays": False}]
    c = Clips(film.load(film_file(tmp_path, shots)), panels={"processes": False})
    with_panels = decode(c.base("end").path).astype(int)[0]
    without = decode(c.base("bare").path).astype(int)[0]
    last = decode(c.base("c").path).astype(int)[-1]
    assert np.abs(with_panels - last).mean() < 4                # as the shot ends
    assert np.abs(without[:, :80] - with_panels[:, :80]).mean() < 4
    assert without[:, 80:].max() < 20 and with_panels[:, 80:].max() > 100
